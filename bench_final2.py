#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""终局配置验证 —— 严格按官方 graft_recipe 步骤 7 的黄金配置，去掉误加的 --kv-mean-center。

黄金配置（recipe 原文）：
  GGML_CUDA_BATCH_INVARIANT=1
  -ngl 99 -fa on -np 1 -ctk q4_0 -ctv q4_0 --jinja
  --spec-type draft-mtp --spec-draft-n-max 1
无 --kv-mean-center（那是 kvmem 路线，与 MTP 冲突）

扫描维度：上下文 × draft KV 类型，外加长前缀 prefill 与功耗采样。
"""
import json, os, subprocess, time, urllib.request

BASE = r"D:\Bonsai-demo"
BINDIR = os.path.join(BASE, "dist", "bonsai2-8gb", "bin")
BIN = os.path.join(BINDIR, "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")
FAT = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf")
os.environ["no_proxy"] = "127.0.0.1"; os.environ["NO_PROXY"] = "127.0.0.1"

K1 = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]
BASE_ARGS = ["-ngl", "99", "-fa", "on", "-np", "1", "--cache-ram", "0", "--jinja",
             "-ctk", "q4_0", "-ctv", "q4_0",
             "--reasoning", "off",
             "--temp", "0.7", "--top-p", "0.80", "--top-k", "20", "--min-p", "0.0",
             "--presence-penalty", "1.5", "--frequency-penalty", "0.0", "--repeat-penalty", "1.0"]

PROMPTS = [
    ("code", "Write a Python quicksort with type hints. Output only the code, no explanation."),
    ("bash", "Write a bash one-liner that finds the ten largest files under /var. Output only the command."),
    ("prose", "In two short paragraphs, explain why the sky appears blue to a curious ten year old."),
]

# (名字, 模型, 上下文, 额外参数)
CONFIGS = [
    ("F1-c32768-draftf16", LEAN, 32768, []),
    ("F2-c40960-draftf16", LEAN, 40960, []),
    ("F3-c32768-draftq4",  LEAN, 32768, ["-ctkd", "q4_0", "-ctvd", "q4_0"]),
    ("F4-c49152-draftf16", LEAN, 49152, []),
]


def sh(a):
    r = subprocess.run(a, capture_output=True)
    return (r.stdout or b"").decode("utf-8", "replace").strip()


def gpu():
    try:
        v = sh(["nvidia-smi", "--query-gpu=memory.used,power.draw,clocks.sm,clocks.mem",
                "--format=csv,noheader"]).split("\n")[0]
        return v
    except Exception:
        return "?"


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
    d = json.loads(urllib.request.urlopen(req, timeout=3600).read())
    tm = d.get("timings", {}) or {}
    dn, da = tm.get("draft_n"), tm.get("draft_n_accepted")
    txt = d["choices"][0]["message"].get("content") or ""
    return {"dec": round(tm.get("predicted_per_second") or 0, 2),
            "pre": round(tm.get("prompt_per_second") or 0, 1),
            "acc": (round(da / dn, 3) if (dn and da is not None) else None),
            "tok": d["usage"]["completion_tokens"], "len": len(txt)}


def longpre(n=6000):
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


env = dict(os.environ)
env["PATH"] = BINDIR + os.pathsep + env["PATH"]
env["GGML_CUDA_BATCH_INVARIANT"] = "1"     # recipe 步骤 7 的硬条件

kill()
print("=== 终局黄金配置验证（无 --kv-mean-center）===", flush=True)
rows = []
for name, model, ctx, extra in CONFIGS:
    print("\n########## %s ##########" % name, flush=True)
    kill(); time.sleep(3)
    logp = os.path.join(BASE, "fx_%s.log" % name)
    with open(logp, "wb") as lg:
        subprocess.Popen([BIN, "-m", model, "-c", str(ctx)] + K1 + extra + BASE_ARGS,
                         stdout=lg, stderr=subprocess.STDOUT, env=env)
    ld = ready()
    if ld is None:
        print("  加载失败（可能显存不足）", flush=True); rows.append((name, "-", "-", "-", "LOADFAIL")); kill(); continue
    print("  加载 %.0fs  GPU[%s]" % (ld, gpu()), flush=True)
    try:
        decs, pres, accs = [], [], []
        for tag, p in PROMPTS:
            r = probe(p)
            decs.append(r["dec"]); pres.append(r["pre"])
            if r["acc"] is not None:
                accs.append(r["acc"])
            print("  %-5s dec %6.2f t/s  pre %6.1f t/s  acc=%-6s  %d tok / %d 字符"
                  % (tag, r["dec"], r["pre"], r["acc"], r["tok"], r["len"]), flush=True)
            time.sleep(0.5)
        lp = longpre()
        print("  长前缀 %s tok: prefill %6.1f t/s  TTFT %.2fs" % (lp["n"], lp["pre"], lp["ttft"]), flush=True)
        print("  结束 GPU[%s]" % gpu(), flush=True)
        avg = sum(decs) / len(decs)
        aa = ("%.3f" % (sum(accs) / len(accs))) if accs else "-"
        rows.append((name, "%.2f" % avg, "%.1f" % (sum(pres) / len(pres)), aa, gpu().split(",")[0]))
    except Exception as e:
        print("  异常 %r" % (e,), flush=True); rows.append((name, "ERR", "ERR", "-", str(e)[:30]))
    kill()

print("\n\n============ 终局黄金配置结果 ============", flush=True)
print("%-22s %-9s %-9s %-9s %s" % ("配置", "dec 均", "pre 均", "接收率", "显存"), flush=True)
for r in rows:
    print("%-22s %-9s %-9s %-9s %s" % r, flush=True)
