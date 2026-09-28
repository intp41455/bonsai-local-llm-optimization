#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
终局基准：自编 sm_120a 版 + #218 内核 + MTP
统一用 recipe 的黄金参数，扫上下文与 K 值。
"""
import json, os, subprocess, sys, time, urllib.request

BASE = r"D:\Bonsai-demo"
BIN = os.path.join(BASE, "dist", "bonsai2-8gb", "bin", "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")
KVMC = os.path.join(M27, "kv-mean-center.gguf")
BINDIR = os.path.dirname(BIN)

os.environ["no_proxy"] = "127.0.0.1"; os.environ["NO_PROXY"] = "127.0.0.1"

P_CODE = "Write a Python quicksort with type hints. Output only the code, no explanation."
P_PROSE = ("In two short paragraphs, explain why the sky appears blue to a curious ten year old.")
P_BASH = ("Write a bash one-liner that finds the ten largest files under /var, sorted descending. "
          "Output only the command.")

SPEC1 = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]
SPEC2 = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "2"]

CONFIGS = [
    ("c32768-K1", ["-ngl", "99", "-c", "32768"] + SPEC1),
    ("c40960-K1", ["-ngl", "99", "-c", "40960"] + SPEC1),
    ("c40960-OFF", ["-ngl", "99", "-c", "40960"]),
    ("c49152-K1", ["-ngl", "99", "-c", "49152"] + SPEC1),
    ("c32768-K2", ["-ngl", "99", "-c", "32768"] + SPEC2),
]

COMMON = ["--host", "127.0.0.1", "--port", "8080", "-a", "bonsai",
          "-fa", "on", "-np", "1", "--cache-ram", "0", "--jinja",
          "--reasoning-effort", "low", "--reasoning-budget", "4096",
          "-ctk", "q4_0", "-ctv", "q4_0", "-ctkd", "q4_0", "-ctvd", "q4_0",
          "--kv-mean-center", KVMC,
          "--temp", "0.7", "--top-p", "0.80", "--top-k", "20", "--min-p", "0.0",
          "--presence-penalty", "1.5", "--frequency-penalty", "0.0", "--repeat-penalty", "1.0"]


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


def probe(p, mx=250):
    body = json.dumps({"model": "bonsai", "messages": [{"role": "user", "content": p}],
                       "max_tokens": mx, "temperature": 0.2}).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=3600).read())
    tm = d.get("timings", {}) or {}
    dn, da = tm.get("draft_n"), tm.get("draft_n_accepted")
    return {"dec": round(tm.get("predicted_per_second") or 0, 2),
            "pre": round(tm.get("prompt_per_second") or 0, 1),
            "tok": d["usage"]["completion_tokens"],
            "wall": round(time.time() - t0, 1),
            "acc": (round(da / dn, 3) if (dn and da is not None) else None)}


def long_prefill(n_tok=4000):
    """长提示前缀填充测试。"""
    filler = "The architecture of modern operating systems involves scheduling, virtual memory, and file systems. "
    p = (filler * (n_tok // 12)) + "\n\nSummarise the above in one sentence."
    body = json.dumps({"model": "bonsai", "messages": [{"role": "user", "content": p}],
                       "max_tokens": 32, "temperature": 0.2}).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=3600).read())
    tm = d.get("timings", {}) or {}
    return {"n_prompt": tm.get("prompt_n"), "pre": round(tm.get("prompt_per_second") or 0, 1),
            "ttft": round(time.time() - t0, 2)}


env = dict(os.environ)
env["PATH"] = BINDIR + os.pathsep + env["PATH"]
env["GGML_CUDA_BATCH_INVARIANT"] = "1"

if not os.path.isfile(BIN):
    sys.exit("缺二进制: %s" % BIN)
if not os.path.isfile(KVMC):
    sys.exit("缺 KV 偏置: %s" % KVMC)

kill()
print("=== GPU 起始 %s ===" % vram(), flush=True)
print("=== 二进制: %s ===" % BIN, flush=True)
rows = []
for name, extra in CONFIGS:
    print("\n########## %s ##########" % name, flush=True)
    kill(); time.sleep(3)
    with open(os.path.join(BASE, "final_%s.log" % name), "wb") as lg:
        subprocess.Popen([BIN, "-m", LEAN] + extra + COMMON, stdout=lg, stderr=subprocess.STDOUT, env=env)
    ld = ready()
    if ld is None:
        print("  加载失败/超时", flush=True); rows.append((name, "-", "-", "-", "-", "LOADFAIL")); kill(); continue
    print("  加载 %.0fs  显存 %s" % (ld, vram()), flush=True)
    try:
        rc = probe(P_CODE); time.sleep(0.6)
        rb = probe(P_BASH); time.sleep(0.6)
        rp = probe(P_PROSE)
        lp = long_prefill()
        for tag, r in [("code", rc), ("bash", rb), ("prose", rp)]:
            print("  %-6s dec %6.2f t/s  pre %6.1f t/s  tok=%4d  acc=%s"
                  % (tag, r["dec"], r["pre"], r["tok"], r["acc"]), flush=True)
        print("  长前缀(%s tok): prefill %6.1f t/s  TTFT %.2fs" % (lp["n_prompt"], lp["pre"], lp["ttft"]), flush=True)
        best = max(rc["dec"], rb["dec"], rp["dec"])
        accs = [r["acc"] for r in (rc, rb, rp) if r["acc"] is not None]
        rows.append((name, vram() or "-", "%.2f" % best, "%.1f" % max(rc["pre"], rb["pre"], rp["pre"]),
                     ("%.3f" % (sum(accs) / len(accs))) if accs else "-",
                     "CLIFF" if best < 5 else "ok"))
    except Exception as e:
        print("  探针异常 %r" % (e,), flush=True)
        rows.append((name, vram() or "-", "ERR", "ERR", "-", str(e)[:36]))
    kill()

print("\n\n================ 终局基准汇总 ================", flush=True)
print("%-12s %-16s %-10s %-11s %-10s %s" % ("配置", "显存", "dec t/s", "pre t/s", "平均接收", "状态"), flush=True)
for r in rows:
    print("%-12s %-16s %-10s %-11s %-10s %s" % r, flush=True)
