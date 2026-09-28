"""在推理进行时同步采样 GPU 状态，定位「同配置不同速度」的原因。

怀疑：显存频率（9001 vs 12001 MHz）或 SM 频率在负载下未升满。
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"D:/Bonsai-demo")
BIN = ROOT / "dist" / "bonsai2-8gb-combo" / "bin"
MODEL = ROOT / "models" / "bonsai2-gguf" / "27B" / "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"

ARGS = [
    "-ngl", "99", "-fa", "on", "-np", "1", "-b", "2048", "-ub", "512",
    "-c", "32768", "-ctk", "q4_0", "-ctv", "q4_0",
    "--jinja", "--metrics", "-n", "24576",
    "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
    "--reasoning-budget", "20480",
    "--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
    "--spec-draft-depth-max", "4096", "-ctkd", "q4_0", "-ctvd", "q4_0",
    "--backend-sampling",
]

PROMPTS = [
    "Write a Python function that merges two sorted lists. Code only.",
    "Write a bash one-liner that finds the 10 largest files under /var.",
    "Explain in one paragraph why the sky is blue.",
]

samples: list[str] = []
stop = False


def sampler() -> None:
    while not stop:
        try:
            o = subprocess.run(
                ["nvidia-smi", "--query-gpu=clocks.sm,clocks.mem,power.draw,"
                 "temperature.gpu,utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5).stdout.strip()
            if o:
                samples.append(o)
        except Exception:
            pass
        time.sleep(0.4)


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


def main() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    time.sleep(3)
    log = open(ROOT / "gs.log", "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    cmd = ([str(BIN / "llama-server.exe"), "-m", str(MODEL),
            "--host", "127.0.0.1", "--port", str(PORT)] + ARGS)
    proc = subprocess.Popen(cmd, cwd=str(BIN), stdout=log,
                            stderr=subprocess.STDOUT, env=env)
    global stop
    try:
        if not wait_ready(proc):
            print("启动失败")
            return
        time.sleep(2)
        # 预热：连续负载让 GPU 进入稳态（避开首次 kernel 编译 + 冷启动调频）
        print("预热中 ...", flush=True)
        for i in range(4):
            post("/completion", {"prompt": "Write a detailed technical explanation "
                                 "of how transformer attention works.", "n_predict": 300,
                                 "temperature": 0.0})
            print(f"  预热 {i+1}/4", flush=True)
        t = threading.Thread(target=sampler, daemon=True)
        t.start()
        print("\n=== 推理中 ===")
        for p in PROMPTS:
            r = post("/completion", {"prompt": p, "n_predict": 400,
                                     "temperature": 0.0, "cache_prompt": False})
            ti = r.get("timings", {})
            print(f"  dec={ti.get('predicted_per_second',0):6.2f} t/s  "
                  f"acc={(ti.get('draft_n_accepted',0)/ti['draft_n']) if ti.get('draft_n') else float('nan'):.3f}")
        stop = True
        time.sleep(1)
        print(f"\n=== GPU 采样 {len(samples)} 次 ===")
        sms, mems, pws, temps = [], [], [], []
        for s in samples:
            p = [x.strip() for x in s.split(",")]
            try:
                sms.append(int(p[0])); mems.append(int(p[1]))
                pws.append(float(p[2])); temps.append(int(p[3]))
            except Exception:
                pass
        if sms:
            print(f"  SM 频率   : {min(sms)} ~ {max(sms)} MHz (峰值 3090)")
            print(f"  显存频率  : {min(mems)} ~ {max(mems)} MHz (峰值 12001)")
            print(f"  功耗      : {min(pws):.1f} ~ {max(pws):.1f} W")
            print(f"  温度      : {min(temps)} ~ {max(temps)} C")
            from collections import Counter
            print(f"  显存频率分布: {Counter(mems).most_common(4)}")
    finally:
        stop = True
        subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
        log.close()


def post(path, payload, timeout=900):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


if __name__ == "__main__":
    main()
