#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""终局基准 v2 —— 自编 sm_120a + #218 内核 + MTP，KV 偏置用自编工具重生成。"""
import hashlib, json, os, subprocess, time, urllib.request

BASE = r"D:\Bonsai-demo"
BINDIR = os.path.join(BASE, "dist", "bonsai2-8gb", "bin")
BIN = os.path.join(BINDIR, "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")
KVMC = os.path.join(M27, "kv-mean-center.gguf")
os.environ["no_proxy"] = "127.0.0.1"; os.environ["NO_PROXY"] = "127.0.0.1"

P_CODE = "Write a Python quicksort with type hints. Output only the code, no explanation."
P_BASH = "Write a bash one-liner that finds the ten largest files under /var. Output only the command."
P_PROSE = "In two short paragraphs, explain why the sky appears blue to a curious ten year old."
K1 = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]

COMMON = ["--host", "127.0.0.1", "--port", "8080", "-a", "bonsai",
          "-fa", "on", "-np", "1", "--cache-ram", "0", "--jinja",
          "-ctk", "q4_0", "-ctv", "q4_0", "-ctkd", "q4_0", "-ctvd", "q4_0",
          "--kv-mean-center", KVMC,
          "--temp", "0.7", "--top-p", "0.80", "--top-k", "20", "--min-p", "0.0",
          "--presence-penalty", "1.5", "--frequency-penalty", "0.0", "--repeat-penalty", "1.0"]

GEN = ["--reasoning", "off"]                                  # 生成任务档（recipe）
AGENT = ["--reasoning-effort", "low", "--reasoning-budget", "4096"]  # 智能体档（recipe）

CONFIGS = [
    ("A-c32768-MTP-K1-gen", LEAN, ["-ngl", "99", "-c", "32768"] + K1 + GEN),
    ("B-c40960-MTP-K1-gen", LEAN, ["-ngl", "99", "-c", "40960"] + K1 + GEN),
    ("C-c32768-off-gen",    LEAN, ["-ngl", "99", "-c", "32768"] + GEN),
    ("D-c32768-MTP-K1-agent", LEAN, ["-ngl", "99", "-c", "32768"] + K1 + AGENT),
]


def sh(a):
    r = subprocess.run(a, capture_output=True)
    return (r.stdout or b"").decode("utf-8", "replace").strip()


def vram():
    return sh(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"]).split("\n")[0]


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


def probe(p, mx=300, temp=0.2):
    body = json.dumps({"model": "bonsai", "messages": [{"role": "user", "content": p}],
                       "max_tokens": mx, "temperature": temp}).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=3600).read())
    tm = d.get("timings", {}) or {}
    dn, da = tm.get("draft_n"), tm.get("draft_n_accepted")
    txt = d["choices"][0]["message"].get("content") or ""
    return {"dec": round(tm.get("predicted_per_second") or 0, 2),
            "pre": round(tm.get("prompt_per_second") or 0, 1),
            "tok": d["usage"]["completion_tokens"], "len": len(txt),
            "wall": round(time.time() - t0, 1),
            "acc": (round(da / dn, 3) if (dn and da is not None) else None)}


def long_prefill(n=5000):
    filler = "The architecture of modern operating systems involves scheduling, virtual memory, and file systems. "
    body = json.dumps({"model": "bonsai",
                       "messages": [{"role": "user", "content": filler * (n // 12) + "\nSummarise in one sentence."}],
                       "max_tokens": 24, "temperature": 0.2}).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=3600).read())
    tm = d.get("timings", {}) or {}
    return {"n": tm.get("prompt_n"), "pre": round(tm.get("prompt_per_second") or 0, 1),
            "ttft": round(time.time() - t0, 2)}


# 偏置指纹（确认已换成自编版生成的）
hv = hashlib.md5(open(KVMC, "rb").read()).hexdigest()
hs = hashlib.md5(open(os.path.join(M27, "kv-mean-center.stock.gguf"), "rb").read()).hexdigest() if os.path.isfile(
    os.path.join(M27, "kv-mean-center.stock.gguf")) else "n/a"
print("KV 偏置 md5: 自编版=%s  stock版=%s  不同=%s" % (hv[:12], hs[:12], hv != hs), flush=True)

env = dict(os.environ)
env["PATH"] = BINDIR + os.pathsep + env["PATH"]
env["GGML_CUDA_BATCH_INVARIANT"] = "1"

kill()
print("=== GPU 起始 %s ===" % vram(), flush=True)
rows = []
for name, model, extra in CONFIGS:
    print("\n########## %s ##########" % name, flush=True)
    kill(); time.sleep(3)
    with open(os.path.join(BASE, "v2_%s.log" % name), "wb") as lg:
        subprocess.Popen([BIN, "-m", model] + extra + COMMON, stdout=lg, stderr=subprocess.STDOUT, env=env)
    ld = ready()
    if ld is None:
        print("  加载失败", flush=True); rows.append((name, "-", "-", "-", "-", "LOADFAIL")); kill(); continue
    print("  加载 %.0fs  显存 %s" % (ld, vram()), flush=True)
    try:
        decs, pres, accs = [], [], []
        for tag, p in [("code", P_CODE), ("bash", P_BASH), ("prose", P_PROSE)]:
            r = probe(p)
            decs.append(r["dec"]); pres.append(r["pre"])
            if r["acc"] is not None:
                accs.append(r["acc"])
            print("  %-6s dec %6.2f t/s  pre %6.1f t/s  tok=%3d 字符=%4d  acc=%s"
                  % (tag, r["dec"], r["pre"], r["tok"], r["len"], r["acc"]), flush=True)
            time.sleep(0.6)
        lp = long_prefill()
        print("  长前缀 %s tok: prefill %6.1f t/s  TTFT %.2fs" % (lp["n"], lp["pre"], lp["ttft"]), flush=True)
        avg = sum(decs) / len(decs)
        rows.append((name, vram() or "-", "%.2f" % avg, "%.1f" % (sum(pres) / len(pres)),
                     ("%.3f" % (sum(accs) / len(accs))) if accs else "-",
                     "CLIFF" if avg < 5 else "ok"))
    except Exception as e:
        print("  探针异常 %r" % (e,), flush=True)
        rows.append((name, vram() or "-", "ERR", "ERR", "-", str(e)[:34]))
    kill()

print("\n\n============ 终局基准 v2 ============", flush=True)
print("%-24s %-16s %-10s %-11s %-10s %s" % ("配置", "显存", "dec 均", "pre 均", "接收率", "状态"), flush=True)
for r in rows:
    print("%-24s %-16s %-10s %-11s %-10s %s" % r, flush=True)
