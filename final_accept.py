"""最终验收 v2：自管服务生命周期（避免父 shell 退出带走子进程）。

在「显存锁满 12001 MHz」状态下，用与交付脚本完全一致的黄金配置启动服务，
跑 4 类提示词，并全程采样 GPU 频率，验证性能是否稳定。
"""
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"D:/Bonsai-demo")
BIN = ROOT / "dist" / "bonsai2-8gb-combo" / "bin"
MODEL = ROOT / "models" / "bonsai2-gguf" / "27B" / "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PORT = 8080
LOG = ROOT / "final_accept.log"

# 与 start_bonsai_8gb.bat 完全一致
ARGS = [
    "-m", str(MODEL),
    "-ngl", "99", "-fa", "on", "-np", "1",
    "-c", "32768", "-b", "2048", "-ub", "512",
    "-ctk", "q4_0", "-ctv", "q4_0",
    "--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
    "--spec-draft-depth-max", "4096",
    "-ctkd", "q4_0", "-ctvd", "q4_0",
    "--backend-sampling",
    "--jinja",
    "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
    "--reasoning-budget", "20480",
    "--reasoning-budget-message", "Now produce the complete answer.",
    "-n", "24576",
    "--temp", "1.0", "--top-p", "0.95", "--top-k", "20",
    "--host", "127.0.0.1", "--port", str(PORT), "--alias", "bonsai-2-27b",
    "--metrics",
]

PROMPTS = [
    ("code",  "Write a Python function that merges two sorted lists into one. "
              "Include type hints and handle duplicates. Code only, no explanation."),
    ("bash",  "Write a bash script that finds all files larger than 100MB under a "
              "directory, sorts them by size, and prints the top 20 with human-readable sizes."),
    ("prose", "Explain in about 150 words why mixed-precision quantization helps run "
              "large language models on consumer GPUs with limited VRAM."),
    ("json",  'Return a JSON array of 8 objects, each with keys "id", "name", "score". '
              'Fill with plausible sample data for a game leaderboard. JSON only.'),
]

samples = []


def kill():
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                   capture_output=True, text=True)


def gpu_sampler(stop_evt):
    while not stop_evt.is_set():
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=clocks.sm,clocks.mem,power.draw,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5).stdout.strip()
            if out:
                samples.append(out)
        except Exception:
            pass
        stop_evt.wait(1.5)


def post(path, payload, timeout=400):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wait_ready(proc, limit=180):
    t0 = time.time()
    while time.time() - t0 < limit:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main():
    kill()
    time.sleep(4)
    log = open(LOG, "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    print("启动服务（黄金配置）...", flush=True)
    proc = subprocess.Popen([str(BIN / "llama-server.exe")] + ARGS,
                            cwd=str(BIN), stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        if not wait_ready(proc):
            print("  !! 启动失败，见", LOG, flush=True)
            return
        print("  服务就绪\n", flush=True)

        # 预热到稳态（关键：让 GPU 进入高负载稳态后再测）
        print("预热中（2×96 token）...", flush=True)
        for _ in range(2):
            post("/completion", {"prompt": "hello", "n_predict": 96, "temperature": 0.0})

        stop = threading.Event()
        threading.Thread(target=gpu_sampler, args=(stop,), daemon=True).start()

        print(f"\n{'='*72}\n### 锁频后最终验收 · 黄金配置\n{'='*72}", flush=True)
        rows = []
        for tag, p in PROMPTS:
            try:
                r = post("/completion", {"prompt": p, "n_predict": 400,
                                         "temperature": 0.0, "cache_prompt": False,
                                         "stream": False})
                t = r.get("timings", {})
                dec = t.get("predicted_per_second", 0.0)
                dn = t.get("draft_n", 0) or 0
                da = t.get("draft_n_accepted", 0) or 0
                acc = (da / dn) if dn else float("nan")
                txt = r.get("content", "") or ""
                rows.append((tag, dec, acc))
                print(f"  {tag:6s}  decode={dec:6.2f} t/s  acc={acc:.3f}  "
                      f"draft={da}/{dn}  生成 {len(txt)} 字符", flush=True)
            except Exception as e:
                print(f"  {tag:6s}  失败: {str(e)[:100]}", flush=True)

        stop.set()
        time.sleep(1.5)

        if rows:
            decs = [x[1] for x in rows]
            accs = [x[2] for x in rows if x[2] == x[2]]
            print(f"\n  {'-'*62}")
            print(f"  平均 decode = {sum(decs)/len(decs):.2f} t/s   "
                  f"峰值 = {max(decs):.2f}   最低 = {min(decs):.2f}")
            if accs:
                print(f"  平均接受率 = {sum(accs)/len(accs):.3f}")

        print(f"\n{'='*72}\n### 全程 GPU 采样（{len(samples)} 次）\n{'='*72}", flush=True)
        sm, mem, pw, tp = [], [], [], []
        for s in samples:
            try:
                a, b, c, d = [x.strip() for x in s.split(",")]
                sm.append(int(a)); mem.append(int(b)); pw.append(float(c)); tp.append(int(d))
            except Exception:
                continue
        if mem:
            print(f"  显存频率: {min(mem)} ~ {max(mem)} MHz")
            print(f"  SM 频率:  {min(sm)} ~ {max(sm)} MHz")
            print(f"  功耗:     {min(pw):.1f} ~ {max(pw):.1f} W")
            print(f"  温度:     {min(tp)} ~ {max(tp)} °C")
            at_max = sum(1 for m in mem if m >= 12001)
            print(f"  满频 12001 占比: {at_max}/{len(mem)} ({100*at_max/len(mem):.0f}%)")

        json.dump({"rows": rows, "samples": samples},
                  open(ROOT / "final_accept.json", "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)
    finally:
        kill()
        log.close()


if __name__ == "__main__":
    main()
