#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""23 补丁 bundle（professorpalmer bonsai-combo）vs 我们的原生 sm_120a 构建。

bundle: sm_75/86/89 机器码 + compute_89 PTX（RTX 50 首次加载 JIT）
       含 cut 7 prefill 修复（pp2048 2x）、FA 直读量化 KV、多列 verify 优化
重点验证：prefill 是否翻倍、n-max 2 是否因 0013 补丁变得更快、能否撑更长上下文
"""
import json, os, subprocess, time, urllib.request

BASE = r"D:\Bonsai-demo"
BINDIR = os.path.join(BASE, "bundle", "bin")
BIN = os.path.join(BINDIR, "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")
os.environ["no_proxy"] = "127.0.0.1"; os.environ["NO_PROXY"] = "127.0.0.1"

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

# (名字, 上下文, 额外参数)
CONFIGS = [
    ("G1-c32768-nmax1", 32768, ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]),
    ("G2-c32768-nmax2", 32768, ["--spec-type", "draft-mtp", "--spec-draft-n-max", "2"]),
    ("G3-c32768-nmax3", 32768, ["--spec-type", "draft-mtp", "--spec-draft-n-max", "3"]),
    ("G4-c40960-nmax2", 40960, ["--spec-type", "draft-mtp", "--spec-draft-n-max", "2"]),
]


def sh(a):
    r = subprocess.run(a, capture_output=True)
    return (r.stdout or b"").decode("utf-8", "replace").strip()


def gpu():
    try:
        return sh(["nvidia-smi", "--query-gpu=memory.used,power.draw,clocks.sm,clocks.mem",
                   "--format=csv,noheader"]).split("\n")[0]
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


def ready(t=900):   # PTX JIT 首次加载可能很久
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


def longpre(n=8000):
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
env["GGML_CUDA_BATCH_INVARIANT"] = "1"

kill()
print("=== 23 补丁 bundle 验证（PTX JIT，首次加载慢）===", flush=True)
rows = []
for name, ctx, spec in CONFIGS:
    print("\n########## %s ##########" % name, flush=True)
    kill(); time.sleep(3)
    logp = os.path.join(BASE, "gx_%s.log" % name)
    with open(logp, "wb") as lg:
        subprocess.Popen([BIN, "-m", LEAN, "-c", str(ctx)] + spec + BASE_ARGS,
                         stdout=lg, stderr=subprocess.STDOUT, env=env)
    ld = ready()
    if ld is None:
        print("  加载失败/OOM", flush=True); rows.append((name, "-", "-", "-", "LOADFAIL")); kill(); continue
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

print("\n\n============ 23 补丁 bundle 结果 ============", flush=True)
print("%-20s %-9s %-9s %-9s %s" % ("配置", "dec 均", "pre 均", "接收率", "显存"), flush=True)
for r in rows:
    print("%-20s %-9s %-9s %-9s %s" % r, flush=True)
