# -*- coding: utf-8 -*-
"""
探测 RTX 5060 Laptop 8GB 上不同 (context, MTP, ngl) 组合的可行上限。
只回答一个问题：能不能把窗口开到 65536，装下 WorkBuddy 发的 48937 token？
"""
import os, sys, time, subprocess, urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT  = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo"
BIN   = os.path.join(ROOT, "bin")
MODEL = r"D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PORT  = 8080
BASE  = "http://127.0.0.1:%d" % PORT

# (tag, ctx, mtp, ngl)
CONFIGS = [
    ("A. MTP off / c65536 / ngl99", 65536, False, 99),
    ("B. MTP on  / c65536 / ngl99", 65536, True,  99),
    ("C. MTP off / c65536 / ngl80", 65536, False, 80),
    ("D. MTP off / c49152 / ngl99", 49152, False, 99),
]


def kill_all():
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                   capture_output=True, encoding="gbk", errors="ignore")
    time.sleep(2)


def args_for(ctx, mtp, ngl):
    a = [os.path.join(BIN, "llama-server.exe"), "-m", MODEL,
         "-ngl", str(ngl), "-fa", "on", "-np", "1",
         "-c", str(ctx), "-b", "2048", "-ub", "512",
         "-ctk", "q4_0", "-ctv", "q4_0",
         "--backend-sampling", "--jinja",
         "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
         "-n", "8192",
         "--temp", "1.0", "--top-p", "0.95", "--top-k", "20",
         "--host", "127.0.0.1", "--port", str(PORT),
         "--alias", "bonsai-2-27b", "--metrics"]
    if mtp:
        a += ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
              "--spec-draft-depth-max", "4096", "-ctkd", "q4_0", "-ctvd", "q4_0"]
    return a


def probe_speed():
    """发一个小请求，返回 (decode_tps, ok)"""
    body = ('{"model":"bonsai-2-27b","messages":[{"role":"user",'
            '"content":"用一句话说明什么是张量。"}],"max_tokens":64,'
            '"chat_template_kwargs":{"enable_thinking":false}}')
    req = urllib.request.Request(BASE + "/v1/chat/completions",
                                 data=body.encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            import json
            d = json.loads(r.read().decode())
        t = d.get("timings", {}) or {}
        return round(t.get("predicted_per_second", 0.0), 2), True
    except Exception as e:
        return 0.0, False


def gpu_mem():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, encoding="gbk", errors="ignore", timeout=15)
        return r.stdout.strip()
    except Exception:
        return "?"


def run_cfg(tag, ctx, mtp, ngl, timeout=200):
    kill_all()
    lg = r"D:\Bonsai-demo\ctxprobe_%d_%s_%d.log" % (ctx, "mtp" if mtp else "nomtp", ngl)
    env = dict(os.environ)
    if mtp:
        env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    f = open(lg, "wb")
    t0 = time.time()
    p = subprocess.Popen(args_for(ctx, mtp, ngl), cwd=BIN, env=env,
                         stdout=f, stderr=subprocess.STDOUT,
                         creationflags=0x8 | 0x200, close_fds=True)

    ready = None
    while time.time() - t0 < timeout:
        if p.poll() is not None:
            break
        try:
            with urllib.request.urlopen(BASE + "/health", timeout=2) as r:
                if '"ok"' in r.read().decode("utf-8", "ignore"):
                    ready = time.time() - t0
                    break
        except Exception:
            pass
        time.sleep(1)

    if ready is None:
        died = p.poll() is not None
        print("  [FAIL] %-30s  %s  耗时 %.0fs" %
              (tag, "进程退出" if died else "就绪超时", time.time() - t0))
        # 抓关键错误行
        try:
            txt = open(lg, "r", encoding="utf-8", errors="ignore").read().splitlines()
            keys = [l for l in txt if any(k in l for k in
                    ("out of memory", "OOM", "failed to allocate",
                     "error", "Error", "abort", "ggml_cuda"))]
            for l in keys[-6:]:
                print("         | " + l.strip()[:150])
        except Exception:
            pass
        try:
            p.kill()
        except Exception:
            pass
        kill_all()
        return False, ""

    tps, ok = probe_speed()
    mem = gpu_mem()
    print("  [ OK ] %-30s  加载 %.0fs  decode %s t/s  显存 %s MiB" %
          (tag, ready, tps if ok else "FAIL", mem))
    kill_all()
    return True, tps


def main():
    print("=" * 78)
    print("  8GB 显存上下文上限探测  (目标: 装下 WorkBuddy 的 48937 token)")
    print("=" * 78)
    for tag, ctx, mtp, ngl in CONFIGS:
        run_cfg(tag, ctx, mtp, ngl)
    print()
    print("探测结束。日志: D:\\Bonsai-demo\\ctxprobe_*.log")


if __name__ == "__main__":
    main()
