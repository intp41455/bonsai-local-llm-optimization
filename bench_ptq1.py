#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PTQ1_0 vs PQ2_0 A/B —— 在 RTX 5060 Laptop 8GB 上复现 sweeps/rtx3060ti-8gb.md 的方法。
每档：启动 -> 等就绪 -> 记录显存 -> 打探针 -> 记录 decode/prefill t/s -> 关闭。
"""
import json, os, subprocess, sys, time, urllib.request

BASE = r"D:\Bonsai-demo"
BIN  = os.path.join(BASE, "bin", "cuda", "llama-server.exe")
M27  = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
PTQ  = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0.gguf")
PQ2  = os.path.join(M27, "Ternary-Bonsai-2-27B-PQ2_0.gguf")

os.environ["no_proxy"] = "127.0.0.1"
os.environ["NO_PROXY"] = "127.0.0.1"

PROMPT = "Write a Python quicksort with type hints, then state its average and worst-case time complexity."


def sh(args):
    """Windows 命令输出可能是 GBK —— 一律按字节取，手动容错解码。"""
    r = subprocess.run(args, capture_output=True)
    return (r.stdout or b"").decode("utf-8", errors="replace").strip()


def vram():
    out = sh(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"])
    return out.split("\n")[0] if out else "?"


def port_alive(timeout=2):
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=timeout).read()
        return True
    except Exception:
        return False


def kill_server():
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    for _ in range(40):
        time.sleep(1)
        if not port_alive():
            time.sleep(2)
            if not port_alive():
                return True
    return False


def wait_ready(timeout=330):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5)
            if json.loads(r.read()).get("status") == "ok":
                return time.time() - t0
        except Exception:
            pass
        time.sleep(3)
    return None


def probe(max_tokens=320, think="none"):
    body = json.dumps({
        "model": "bonsai",
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "top_p": 0.8,
        "reasoning_effort": think,
    }).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8080/v1/chat/completions",
        data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    wall = time.time() - t0
    tm = d.get("timings", {}) or {}
    return {
        "tok": d["usage"]["completion_tokens"],
        "wall": round(wall, 2),
        "prefill_tps": round(tm.get("prompt_per_second") or 0.0, 1),
        "decode_tps": round(tm.get("predicted_per_second") or 0.0, 2),
        "n_prompt": tm.get("prompt_n"),
    }


CONFIGS = [
    ("A 基线 PQ2_0  ngl52  c16384 (现状)", PQ2, ["-ngl", "52", "-c", "16384"]),
    ("B PTQ1_0 ngl99 c32768",              PTQ, ["-ngl", "99", "-c", "32768"]),
    ("C PTQ1_0 ngl99 c65536",              PTQ, ["-ngl", "99", "-c", "65536"]),
    ("D PTQ1_0 ngl99 c98304",              PTQ, ["-ngl", "99", "-c", "98304"]),
    ("E PTQ1_0 ngl99 c131072",             PTQ, ["-ngl", "99", "-c", "131072"]),
    ("F PTQ1_0 ngl99 c262144",             PTQ, ["-ngl", "99", "-c", "262144"]),
]

COMMON = ["--host", "127.0.0.1", "--port", "8080", "-a", "bonsai-27b",
          "-fa", "on", "-np", "1", "--cache-ram", "24576",
          "--jinja", "--reasoning-effort", "medium",
          "-ctk", "q4_0", "-ctv", "q4_0",
          "--temp", "1.0", "--top-p", "0.95", "--top-k", "20", "--min-p", "0.05"]

env = dict(os.environ)
env["PATH"] = os.path.join(BASE, "bin", "cuda") + os.pathsep + env["PATH"]
env["BONSAI_KV4"] = "1"

results = []
kill_server()
print("=== GPU 空闲: %s ===" % vram(), flush=True)

for name, model, extra in CONFIGS:
    print("\n########## %s ##########" % name, flush=True)
    kill_server()
    time.sleep(3)
    cmd = [BIN, "-m", model] + extra + COMMON
    log = open(os.path.join(BASE, "bench_ptq1_%s.log" % name.split()[0]), "wb")
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
    load = wait_ready()
    if load is None:
        print("  加载失败/超时 -> 记为 FAIL", flush=True)
        results.append((name, "FAIL", "-", "-", "-"))
        kill_server()
        log.close()
        continue
    used = vram()
    print("  加载耗时 %.0fs  显存 %s" % (load, used), flush=True)
    try:
        r1 = probe()
        print("  探针1: decode %.2f t/s  prefill %.1f t/s  tok=%d wall=%.1fs"
              % (r1["decode_tps"], r1["prefill_tps"], r1["tok"], r1["wall"]), flush=True)
        r2 = probe()
        print("  探针2: decode %.2f t/s  prefill %.1f t/s  tok=%d wall=%.1fs"
              % (r2["decode_tps"], r2["prefill_tps"], r2["tok"], r2["wall"]), flush=True)
        best = max(r1["decode_tps"], r2["decode_tps"])
        results.append((name, used, "%.2f" % best, "%.1f" % max(r1["prefill_tps"], r2["prefill_tps"]), "ok"))
    except Exception as e:
        print("  探针异常: %r" % (e,), flush=True)
        results.append((name, used, "ERR", "ERR", str(e)[:60]))
    kill_server()
    log.close()

print("\n\n================ 汇总 ================", flush=True)
print("%-40s %-14s %-12s %-12s" % ("配置", "显存", "decode t/s", "prefill t/s"), flush=True)
for n, v, d, p_, s in results:
    print("%-40s %-14s %-12s %-12s" % (n, v, d, p_), flush=True)
