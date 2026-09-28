"""深度扫描 v2：用【真实技术文档】作填充，让模型真的有内容可续写。

教训：用 "alpha beta gamma" 之类的重复无意义文本填充，模型会立即 EOS
（服务日志表现为 `eval time = 0.00 ms / 1 tokens`），永远测不到 decode。
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"D:/Bonsai-demo")
BIN = ROOT / "dist" / "bonsai2-8gb-combo" / "bin"
MODEL = ROOT / "models" / "bonsai2-gguf" / "27B" / "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
DOC = ROOT / "surgery" / "docs" / "QUALITY.md"
PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"

COMMON = [
    "-ngl", "99", "-fa", "on", "-np", "1", "-b", "2048", "-ub", "512",
    "-c", "32768", "-ctk", "q4_0", "-ctv", "q4_0",
    "--jinja", "--metrics", "--backend-sampling", "-n", "24576",
    "--chat-template-kwargs", '{"reasoning_effort":"low","enable_thinking":false}',
    "--reasoning-budget", "20480",
]

# 递增顺序：后面的请求前缀包含前面的，可复用 KV，加快 prefill
# 1 份 QUALITY.md ≈ 5k token；7 份会超 c32768，故最多到 5 份
COPIES = [1, 2, 3, 4, 5]
TAIL = ("\n\n---\n\nTask: summarize the technical findings above in at least "
        "150 words, covering the measured numbers.\n\nSummary:\n")

DOC_CACHE = None


def doc() -> str:
    global DOC_CACHE
    if DOC_CACHE is None:
        t = DOC.read_text(encoding="utf-8", errors="replace")
        DOC_CACHE = t
    return DOC_CACHE


def kill() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    time.sleep(3)


def wait_ready(proc, timeout=420) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def post(path, payload, timeout=1800):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def run(tag: str, spec: list[str], depth_max: int) -> dict:
    print(f"\n{'='*64}\n### {tag}  (spec-depth-max={depth_max})\n{'='*64}", flush=True)
    log = open(ROOT / f"dp2_{tag}.log", "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    extra = list(spec)
    if spec and depth_max:
        extra += ["--spec-draft-depth-max", str(depth_max)]
    cmd = ([str(BIN / "llama-server.exe"), "-m", str(MODEL),
            "--host", "127.0.0.1", "--port", str(PORT)] + COMMON + extra)
    proc = subprocess.Popen(cmd, cwd=str(BIN), stdout=log,
                            stderr=subprocess.STDOUT, env=env)
    out = {"tag": tag, "depth_max": depth_max, "rows": []}
    cum = 0
    try:
        if not wait_ready(proc):
            print("  !! 启动失败", flush=True)
            return out
        time.sleep(2)
        for c in COPIES:
            try:
                p = doc() * c + TAIL
                r = post("/completion", {"prompt": p, "n_predict": 250,
                                         "temperature": 0.0, "cache_prompt": True,
                                         "stream": False})
                t = r.get("timings", {})
                pn = t.get("prompt_n", 0)
                pdn = t.get("predicted_n", 0)
                cum += pn + pdn
                dec = t.get("predicted_per_second", 0.0)
                dn = t.get("draft_n", 0) or 0
                da = t.get("draft_n_accepted", 0) or 0
                acc = (da / dn) if dn else float("nan")
                txt = r.get("content", "") or ""
                out["rows"].append({"copies": c, "new": pn, "depth": cum,
                                    "decode": dec, "acc": acc, "chars": len(txt)})
                print(f"  累计深度 {cum:6d}  dec={dec:6.2f} t/s  acc={acc:.3f}  "
                      f"生成 {len(txt)} 字符", flush=True)
            except Exception as e:
                print(f"  copies={c} 失败: {str(e)[:80]}", flush=True)
    finally:
        kill()
        log.close()
    return out


def main() -> None:
    on = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
          "-ctkd", "q4_0", "-ctvd", "q4_0"]
    a = run("on-dm0", on, 0)
    b = run("off", [], 0)
    c = run("on-dm4096", on, 4096)
    print(f"\n{'='*64}\n### 深度对比\n{'='*64}")
    print(f"{'深度':>8} {'关草稿':>9} {'开草稿':>9} {'比(无截断)':>11} "
          f"{'开草稿+dm4096':>14} {'比(dm4096)':>11}")
    for x, y, z in zip(a["rows"], b["rows"], c["rows"]):
        r1 = (x["decode"] / y["decode"]) if y["decode"] else 0
        r2 = (z["decode"] / y["decode"]) if y["decode"] else 0
        print(f"{x['depth']:>8} {y['decode']:>9.2f} {x['decode']:>9.2f} "
              f"{r1:>10.2f}x {z['decode']:>14.2f} {r2:>10.2f}x")
    (ROOT / "depth2_result.json").write_text(
        json.dumps({"on": a, "off": b, "on_dm4096": c}, indent=2,
                   ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
