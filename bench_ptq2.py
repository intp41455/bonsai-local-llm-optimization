#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定向扫描：找出 RTX 5060 Laptop 8GB 上 PTQ1_0「-ngl 99 全卸载」的真实上下文悬崖，
并检验两个假设：
  H1 计算缓冲（n_batch）撑爆显存 -> 降 -b/-ub 能否解锁大窗口
  H2 q4_0 KV 的 Flash-Attention 快路在长 n_kv 失效 -> 换 q8_0/f16 KV 是否恢复正常
"""
import json, os, subprocess, sys, time, urllib.request

BASE = r"D:\Bonsai-demo"
BIN = os.path.join(BASE, "bin", "cuda", "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
PTQ = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0.gguf")

os.environ["no_proxy"] = "127.0.0.1"
os.environ["NO_PROXY"] = "127.0.0.1"

PROMPT = "Write a Python quicksort with type hints, then state its average and worst-case time complexity."


def sh(args):
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


def wait_ready(timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5)
            if json.loads(r.read()).get("status") == "ok":
                return time.time() - t0
        except Exception:
            pass
        time.sleep(2)
    return None


def probe(max_tokens=160):
    body = json.dumps({
        "model": "bonsai",
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": max_tokens, "temperature": 0.7, "top_p": 0.8,
        "reasoning_effort": "none",
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=900).read())
    tm = d.get("timings", {}) or {}
    return round(tm.get("predicted_per_second") or 0.0, 2), round(time.time() - t0, 1)


CONFIGS = [
    # name, extra args, kt, vt
    ("P1 ngl99 c49152  KV=q4_0  b默认", ["-ngl", "99", "-c", "49152"], "q4_0", "q4_0"),
    ("P2 ngl99 c98304  KV=q4_0  b512/ub128", ["-ngl", "99", "-c", "98304", "-b", "512", "-ub", "128"], "q4_0", "q4_0"),
    ("P3 ngl99 c98304  KV=q8_0  b默认", ["-ngl", "99", "-c", "98304"], "q8_0", "q8_0"),
    ("P4 ngl99 c131072 KV=q4_0  b512/ub128", ["-ngl", "99", "-c", "131072", "-b", "512", "-ub", "128"], "q4_0", "q4_0"),
    ("P5 ngl99 c65536  KV=q4_0  b默认(复测)", ["-ngl", "99", "-c", "65536"], "q4_0", "q4_0"),
]

results = []
kill_server()
print("=== 起始显存: %s ===" % vram(), flush=True)

for name, extra, kt, vt in CONFIGS:
    print("\n########## %s ##########" % name, flush=True)
    kill_server()
    time.sleep(3)
    cmd = ([BIN, "-m", PTQ] + extra +
           ["--host", "127.0.0.1", "--port", "8080", "-a", "bonsai-27b",
            "-fa", "on", "-np", "1", "--cache-ram", "24576", "--jinja",
            "--reasoning-effort", "medium", "-ctk", kt, "-ctv", vt,
            "--temp", "1.0", "--top-p", "0.95", "--top-k", "20", "--min-p", "0.05"])
    log = open(os.path.join(BASE, "scan_%s.log" % name.split()[0]), "wb")
    env = dict(os.environ)
    env["PATH"] = os.path.join(BASE, "bin", "cuda") + os.pathsep + env["PATH"]
    env["BONSAI_KV4"] = "1"
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
    load = wait_ready()
    if load is None:
        print("  加载失败/超时 -> FAIL", flush=True)
        results.append((name, "FAIL", "-", "-"))
        kill_server(); log.close(); continue
    used = vram()
    print("  加载 %.0fs  显存 %s" % (load, used), flush=True)
    try:
        d1, w1 = probe(); print("  探针1: %.2f t/s  (%.1fs)" % (d1, w1), flush=True)
        d2, w2 = probe(); print("  探针2: %.2f t/s  (%.1fs)" % (d2, w2), flush=True)
        results.append((name, used, "%.2f" % max(d1, d2), "ok"))
    except Exception as e:
        print("  异常 %r" % (e,), flush=True)
        results.append((name, used, "ERR", str(e)[:40]))
    log.close()
    fitwarn = sh(["grep", "-c", "failed to fit params", os.path.join(BASE, "scan_%s.log" % name.split()[0])])
    print("  fit 警告条数: %s" % fitwarn, flush=True)
    kill_server()

print("\n\n============ 汇总 ============", flush=True)
for n, v, d, s in results:
    print("%-40s %-18s %-8s %s" % (n, v, d, s), flush=True)
