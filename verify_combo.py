"""bonsai-combo 构建验收：官方黄金配置在 RTX 5060 Laptop 8GB 上的落地实测。

对比档位：
  A 官方黄金     : K=2 + depth-max 24576 + backend-sampling
  B 单列对照     : K=1 + depth-max 24576 + backend-sampling
  C 无深度截断   : K=2 不带 depth-max
  D 上下文探边界 : K=2 + c40960（8GB+MTP 的硬上限探测）

关键：绝不加 --kv-mean-center（那是 kvmem 路线，与 MTP 冲突，会把接受率打到 0）。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"D:/Bonsai-demo")
# 必须用部署目录：原始 build-win/bin 缺 cudart/cublas 运行时，进程会静默退出（无日志）
BIN = ROOT / "dist" / "bonsai2-8gb-combo" / "bin"
MODEL = ROOT / "models" / "bonsai2-gguf" / "27B" / "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"

COMMON = [
    "-ngl", "99", "-fa", "on", "-np", "1", "-b", "2048", "-ub", "512",
    "-ctk", "q4_0", "-ctv", "q4_0",
    "--jinja", "--metrics",
    "--temp", "1.0", "--top-p", "0.95", "--top-k", "20",
    "-n", "24576",
    "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
    "--reasoning-budget", "20480",
    "--reasoning-budget-message", "Now produce the complete answer.",
]


def spec(nmax: int, depth: int, bs: bool) -> list[str]:
    a = ["--spec-type", "draft-mtp", "--spec-draft-n-max", str(nmax),
         "-ctkd", "q4_0", "-ctvd", "q4_0"]
    if depth:
        a += ["--spec-draft-depth-max", str(depth)]
    if bs:
        a += ["--backend-sampling"]
    return a


CONFIGS = [
    ("A-K2-dm24576-bs", ["-c", "32768"] + spec(2, 24576, True)),
    # 最终交付配置：K=1 + 实测拐点 4096
    ("B-K1-dm4096-bs",  ["-c", "32768"] + spec(1, 4096, True)),
    ("C-K2-nodm",       ["-c", "32768"] + spec(2, 0, True)),
    ("D-K2-c40960",     ["-c", "40960"] + spec(2, 24576, True)),
]

PROMPTS = [
    ("code",  "Write a Python function that merges two sorted lists. Code only."),
    ("bash",  "Write a bash one-liner that finds the 10 largest files under /var."),
    ("prose", "Explain in one paragraph why the sky is blue."),
]


def kill() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                   capture_output=True)
    time.sleep(3)


def vram() -> int:
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10).stdout
        return int(o.strip().split("\n")[0])
    except Exception:
        return -1


def wait_ready(proc: subprocess.Popen, timeout: int = 420) -> bool:
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


def post(path: str, payload: dict, timeout: int = 900) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def run_cfg(name: str, extra: list[str]) -> dict:
    print(f"\n{'='*66}\n### {name}\n{'='*66}", flush=True)
    log = open(ROOT / f"vc_{name}.log", "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    cmd = [str(BIN / "llama-server.exe"), "-m", str(MODEL),
           "--host", "127.0.0.1", "--port", str(PORT)] + COMMON + extra
    proc = subprocess.Popen(cmd, cwd=str(BIN), stdout=log, stderr=subprocess.STDOUT,
                            env=env)
    out = {"name": name, "rows": [], "peak_vram": -1, "ok": False}
    try:
        if not wait_ready(proc):
            print("  !! 服务未就绪 / 崩溃", flush=True)
            return out
        out["ok"] = True
        time.sleep(2)
        v = vram()
        print(f"  加载后显存 {v} MiB", flush=True)
        for tag, prompt in PROMPTS:
            try:
                t0 = time.time()
                r = post("/completion", {
                    "prompt": prompt, "n_predict": 400, "temperature": 0.0,
                    "cache_prompt": False, "stream": False})
                el = time.time() - t0
                t = r.get("timings", {})
                dec = t.get("predicted_per_second", 0.0)
                pre = t.get("prompt_per_second", 0.0)
                dn = t.get("draft_n", 0) or 0
                da = t.get("draft_n_accepted", 0) or 0
                acc = (da / dn) if dn else float("nan")
                ntok = t.get("predicted_n", 0)
                text = r.get("content", "") or ""
                row = {"tag": tag, "decode": dec, "prefill": pre,
                       "acc": acc, "draft_n": dn, "pred_n": ntok,
                       "chars": len(text), "wall": el}
                out["rows"].append(row)
                print(f"  {tag:6s} dec={dec:6.2f} t/s  pre={pre:7.1f} t/s  "
                      f"acc={acc:.3f}  draft={dn}  tok={ntok}  ch={len(text)}",
                      flush=True)
            except Exception as e:
                print(f"  {tag:6s} 失败: {str(e)[:90]}", flush=True)
            v = max(v, vram())
        out["peak_vram"] = v
        print(f"  峰值显存 {v} MiB", flush=True)
    finally:
        kill()
        log.close()
    return out


def main() -> None:
    combos = sys.argv[1:] or [c[0] for c in CONFIGS]
    results = []
    for name, extra in CONFIGS:
        if name not in combos:
            continue
        results.append(run_cfg(name, extra))
    print(f"\n{'='*66}\n### 汇总\n{'='*66}")
    for r in results:
        if not r["rows"]:
            print(f"{r['name']:18s} 无数据 (ok={r['ok']})")
            continue
        ds = [x["decode"] for x in r["rows"]]
        accs = [x["acc"] for x in r["rows"] if x["acc"] == x["acc"]]
        print(f"{r['name']:18s} 平均 {sum(ds)/len(ds):6.2f} t/s  "
              f"峰值 {max(ds):6.2f}  "
              f"acc {sum(accs)/len(accs) if accs else float('nan'):.3f}  "
              f"VRAM {r['peak_vram']} MiB")
    (ROOT / "verify_combo_result.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n结果已写入 verify_combo_result.json")


if __name__ == "__main__":
    main()
