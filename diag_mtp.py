#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定向诊断：为什么 MTP 接收率只有 0.05-0.11（官方 0.85）。"""
import json, os, subprocess, sys, time, urllib.request

BASE = r"D:\Bonsai-demo"
BIN = os.path.join(BASE, "dist", "bonsai2-8gb", "bin", "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")
FAT = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf")
KVMC = os.path.join(M27, "kv-mean-center.gguf")
BINDIR = os.path.dirname(BIN)
os.environ["no_proxy"] = "127.0.0.1"; os.environ["NO_PROXY"] = "127.0.0.1"

P_CODE = "Write a Python quicksort with type hints. Output only the code, no explanation."
K1 = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]

BASE_ARGS = ["--host", "127.0.0.1", "--port", "8080", "-a", "bonsai",
             "-fa", "on", "-np", "1", "--cache-ram", "0", "--jinja",
             "-ctk", "q4_0", "-ctv", "q4_0",
             "--temp", "0.7", "--top-p", "0.80", "--top-k", "20", "--min-p", "0.0",
             "--presence-penalty", "1.5", "--frequency-penalty", "0.0", "--repeat-penalty", "1.0"]

DRAFT_KV = ["-ctkd", "q4_0", "-ctvd", "q4_0"]

CONFIGS = [
    # 名称, 模型, 额外参数, 是否带 KV 偏置
    ("F1-FAT-c32k",        FAT,  ["-ngl", "99", "-c", "32768"] + K1 + DRAFT_KV, True),
    ("F2-LEAN-f16draft",   LEAN, ["-ngl", "99", "-c", "32768"] + K1,            True),
    ("F3-LEAN-nokvbias",   LEAN, ["-ngl", "99", "-c", "32768"] + K1,            False),
    ("F4-LEAN-f16-nokvb",  LEAN, ["-ngl", "99", "-c", "32768"] + K1,            False),
]


def sh(a):
    r = subprocess.run(a, capture_output=True)
    return (r.stdout or b"").decode("utf-8", "replace").strip()


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


def probe(p, mx=250, temp=0.2):
    body = json.dumps({"model": "bonsai", "messages": [{"role": "user", "content": p}],
                       "max_tokens": mx, "temperature": temp}).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=3600).read())
    tm = d.get("timings", {}) or {}
    return {"dec": round(tm.get("predicted_per_second") or 0, 2),
            "acc": tm.get("draft_n_accepted"), "dn": tm.get("draft_n"),
            "txt": (d["choices"][0]["message"]["content"] or "")[:120].replace("\n", " ")}


env = dict(os.environ)
env["PATH"] = BINDIR + os.pathsep + env["PATH"]
env["GGML_CUDA_BATCH_INVARIANT"] = "1"

kill()
print("=== 诊断 MTP 接收率 ===", flush=True)
for name, model, extra, use_kv in CONFIGS:
    if not os.path.isfile(model):
        print("  %-20s 模型缺失" % name, flush=True); continue
    kill(); time.sleep(3)
    args = [BIN, "-m", model] + extra + BASE_ARGS
    if use_kv:
        args += ["--kv-mean-center", KVMC]
    with open(os.path.join(BASE, "diag_%s.log" % name), "wb") as lg:
        subprocess.Popen(args, stdout=lg, stderr=subprocess.STDOUT, env=env)
    ld = ready()
    if ld is None:
        print("  %-20s 加载失败" % name, flush=True); kill(); continue
    try:
        r = probe(P_CODE, temp=0.0)
        a = (r["acc"] / r["dn"]) if (r["dn"] and r["acc"] is not None) else None
        print("  %-20s dec %6.2f t/s  接收率 %s (%s/%s)  样例: %s"
              % (name, r["dec"], ("%.3f" % a) if a is not None else "-", r["acc"], r["dn"], r["txt"][:70]), flush=True)
    except Exception as e:
        print("  %-20s 探针异常 %r" % (name, e), flush=True)
    kill()
print("\n=== 完成 ===", flush=True)
