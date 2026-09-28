#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MTP 接收率干净 A/B：变量只有「二进制」和「KV 偏置」。
思考参数严格对齐（--reasoning-effort low --reasoning-budget 4096），并校验实际输出文本。"""
import json, os, subprocess, time, urllib.request

BASE = r"D:\Bonsai-demo"
OURS = os.path.join(BASE, "dist", "bonsai2-8gb", "bin", "llama-server.exe")
STOCK = os.path.join(BASE, "bin", "cuda", "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")
KVMC = os.path.join(M27, "kv-mean-center.gguf")

os.environ["no_proxy"] = "127.0.0.1"; os.environ["NO_PROXY"] = "127.0.0.1"
P = "Write a Python quicksort with type hints. Output only the code, no explanation."
K1 = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]
ARGS = ["-m", LEAN, "-ngl", "99", "-c", "32768"] + K1 + [
    "--host", "127.0.0.1", "--port", "8080", "-a", "bonsai",
    "-fa", "on", "-np", "1", "--cache-ram", "0", "--jinja",
    "--reasoning-effort", "low", "--reasoning-budget", "4096",
    "-ctk", "q4_0", "-ctv", "q4_0", "-ctkd", "q4_0", "-ctvd", "q4_0",
    "--temp", "0.7", "--top-p", "0.80", "--top-k", "20", "--min-p", "0.0",
    "--presence-penalty", "1.5", "--frequency-penalty", "0.0", "--repeat-penalty", "1.0"]


def alive():
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2).read(); return True
    except Exception:
        return False


def kill():
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    for _ in range(40):
        time.sleep(1)
        if not alive():
            time.sleep(2)
            if not alive(): return True
    return False


def ready(t=420):
    t0 = time.time()
    while time.time() - t0 < t:
        try:
            if json.loads(urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5).read()).get("status") == "ok":
                return time.time() - t0
        except Exception:
            pass
        time.sleep(3)
    return None


def probe():
    body = json.dumps({"model": "bonsai", "messages": [{"role": "user", "content": P}],
                       "max_tokens": 250, "temperature": 0.2}).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    tm = d.get("timings", {}) or {}
    txt = (d["choices"][0]["message"].get("content") or "")
    return {"dec": round(tm.get("predicted_per_second") or 0, 2),
            "acc": tm.get("draft_n_accepted"), "dn": tm.get("draft_n"),
            "n": d["usage"]["completion_tokens"], "len": len(txt)}


CASES = [
    ("我们的构建 + 偏置", OURS, True),
    ("我们的构建 无偏置", OURS, False),
    ("stock 二进制 + 偏置", STOCK, True),
    ("stock 二进制 无偏置", STOCK, False),
]

kill()
print("=== MTP 接收率干净对照（c32768, K=1, reasoning=low/4096）===", flush=True)
for name, binp, use_kv in CASES:
    kill(); time.sleep(3)
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(binp) + os.pathsep + env["PATH"]
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    cmd = [binp] + ARGS + (["--kv-mean-center", KVMC] if use_kv else [])
    with open(os.path.join(BASE, "ab_%s.log" % name.replace(" ", "_")), "wb") as lg:
        subprocess.Popen(cmd, stdout=lg, stderr=subprocess.STDOUT, env=env)
    if ready() is None:
        print("  %-22s 加载失败" % name, flush=True); kill(); continue
    try:
        r = probe()
        a = (r["acc"] / r["dn"]) if (r["dn"] and r["acc"] is not None) else None
        print("  %-22s dec %6.2f t/s  接收率 %-7s (%s/%s)  输出 %d tok / %d 字符"
              % (name, r["dec"], ("%.3f" % a) if a is not None else "-", r["acc"], r["dn"], r["n"], r["len"]), flush=True)
    except Exception as e:
        print("  %-22s 异常 %r" % (name, e), flush=True)
    kill()
print("=== 完成 ===", flush=True)
