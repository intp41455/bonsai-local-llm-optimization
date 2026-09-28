"""深度扫描：验证 --spec-draft-depth-max 的拐点，确定 8GB / c32768 下的最优值。

方法：用可控长 prompt 把上下文填到目标深度，读回 timings.prompt_n 作为真实深度，
对比「开草稿」与「关草稿」在各深度的 decode。
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
PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"

COMMON = [
    "-ngl", "99", "-fa", "on", "-np", "1", "-b", "2048", "-ub", "512",
    "-c", "32768", "-ctk", "q4_0", "-ctv", "q4_0",
    "--jinja", "--metrics", "--backend-sampling", "-n", "24576",
    # 关思考：深上下文下 medium 档会把输出全耗在 <think> 里，测不到 decode
    "--chat-template-kwargs", '{"reasoning_effort":"low","enable_thinking":false}',
    "--reasoning-budget", "20480",
]

# 目标深度（近似 token）：英文单词约 1 token
DEPTHS = [1024, 12288, 26624]
FILLER = "alpha beta gamma delta epsilon zeta eta theta iota kappa "
ASK = ("\n\nWrite a detailed technical explanation, at least 120 words, "
       "of how a transformer attention head computes its output.")


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


def make_prompt(depth: int, uniq: str) -> str:
    """带唯一 sentinel，强制完整 prefill（避免 slot 的 LCP 前缀复用污染测量）。"""
    reps = max(1, depth // 10)
    return f"[[{uniq}]]\n" + FILLER * reps + ASK


def run(tag: str, spec: list[str], depth_max: int) -> dict:
    print(f"\n{'='*64}\n### {tag}  (depth-max={depth_max})\n{'='*64}", flush=True)
    log = open(ROOT / f"dp_{tag}.log", "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    cmd = ([str(BIN / "llama-server.exe"), "-m", str(MODEL),
            "--host", "127.0.0.1", "--port", str(PORT)] + COMMON + spec)
    proc = subprocess.Popen(cmd, cwd=str(BIN), stdout=log,
                            stderr=subprocess.STDOUT, env=env)
    out = {"tag": tag, "depth_max": depth_max, "rows": []}
    try:
        if not wait_ready(proc):
            print("  !! 启动失败", flush=True)
            return out
        time.sleep(2)
        for i, d in enumerate(DEPTHS):
            try:
                r = post("/completion", {"prompt": make_prompt(d, f"{tag}-{i}"),
                                         "n_predict": 200,
                                         "temperature": 0.0, "cache_prompt": False,
                                         "stream": False})
                t = r.get("timings", {})
                pn = t.get("prompt_n", 0)
                dec = t.get("predicted_per_second", 0.0)
                dn = t.get("draft_n", 0) or 0
                da = t.get("draft_n_accepted", 0) or 0
                acc = (da / dn) if dn else float("nan")
                out["rows"].append({"target": d, "depth": pn, "decode": dec, "acc": acc})
                print(f"  深度 {pn:6d}  dec={dec:6.2f} t/s  acc={acc:.3f}", flush=True)
            except Exception as e:
                print(f"  深度 {d} 失败: {str(e)[:80]}", flush=True)
    finally:
        kill()
        log.close()
    return out


def main() -> None:
    spec_on = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
               "-ctkd", "q4_0", "-ctvd", "q4_0"]
    a = run("on-dm0", spec_on, 0)
    b = run("off", [], 0)
    print(f"\n{'='*64}\n### 深度对比\n{'='*64}")
    print(f"{'深度':>8} {'关草稿':>10} {'开草稿':>10} {'加速比':>8} {'接受率':>8}")
    for x, y in zip(a["rows"], b["rows"]):
        ratio = (x["decode"] / y["decode"]) if y["decode"] else 0
        print(f"{x['depth']:>8} {y['decode']:>10.2f} {x['decode']:>10.2f} "
              f"{ratio:>7.2f}x {x['acc']:>8.3f}")
    (ROOT / "depth_result.json").write_text(
        json.dumps({"on": a, "off": b}, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
