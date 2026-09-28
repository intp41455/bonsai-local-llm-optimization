"""跑官方 toolcall_stress.py：原生 tools vs JSON 注入，两个 arm 的失败率对比。

自管服务生命周期（父 shell 退出会带走进程组，这是踩过的坑）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"D:/Bonsai-demo")
BIN = ROOT / "dist" / "bonsai2-8gb-combo" / "bin"
MODEL = ROOT / "models" / "bonsai2-gguf" / "27B" / "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"

COMMON = [
    "-m", str(MODEL), "-ngl", "99", "-fa", "on", "-np", "1",
    "-c", "32768", "-b", "2048", "-ub", "512",
    "-ctk", "q4_0", "-ctv", "q4_0",
    "--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
    "--spec-draft-depth-max", "4096",
    "-ctkd", "q4_0", "-ctvd", "q4_0",
    "--backend-sampling", "--jinja", "--metrics",
    "--alias", "bonsai-2-27b",
    "--temp", "1.0", "--top-p", "0.95", "--top-k", "20",
    "-n", "24576",
    "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
    "--reasoning-budget", "20480",
    "--host", "127.0.0.1", "--port", str(PORT),
]


def kill() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    time.sleep(3)


def wait_ready(proc, timeout: int = 420) -> bool:
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


def main() -> None:
    n = sys.argv[1] if len(sys.argv) > 1 else "2"
    out = ROOT / "toolcall_stress.json"
    log = open(ROOT / "tc_server.log", "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    print("启动服务...", flush=True)
    proc = subprocess.Popen([str(BIN / "llama-server.exe")] + COMMON,
                            cwd=str(BIN), stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        if not wait_ready(proc):
            print("!! 服务未就绪", flush=True)
            return
        print("就绪。开始压力测试 (arm A=原生tools, B=JSON注入)...\n", flush=True)
        r = subprocess.run(
            [sys.executable, "-u", str(ROOT / "surgery" / "bench" / "toolcall_stress.py"),
             "--base", BASE, "--n", n, "--arms", "A,B",
             "--out", str(out)],
            cwd=str(ROOT / "surgery"))
        print(f"\n[rc={r.returncode}]", flush=True)
    finally:
        kill()
        log.close()


if __name__ == "__main__":
    main()
