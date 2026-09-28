#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""隔离三个变量对 MTP 接受率的影响：
   GGML_CUDA_BATCH_INVARIANT (inv)  ×  --kv-mean-center (mc)  ×  LLAMA_ATTN_ROT_DISABLE (rot)

全部：LEAN + K1 + c32768 + -ctk/-ctv/-ctkd/-ctvd 全 q4_0（= 官方 model card 配置）+ reasoning off
"""
import json, os, subprocess, time, urllib.request

BASE = r"D:\Bonsai-demo"
BINDIR = os.path.join(BASE, "dist", "bonsai2-8gb", "bin")
BIN = os.path.join(BINDIR, "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")
KVMC = os.path.join(M27, "kv-mean-center.gguf")
os.environ["no_proxy"] = "127.0.0.1"; os.environ["NO_PROXY"] = "127.0.0.1"

K1 = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]
ARGS = ["-m", LEAN, "-ngl", "99", "-c", "32768"] + K1 + [
    "--host", "127.0.0.1", "--port", "8080", "-a", "bonsai",
    "-fa", "on", "-np", "1", "--cache-ram", "0", "--jinja",
    "-ctk", "q4_0", "-ctv", "q4_0", "-ctkd", "q4_0", "-ctvd", "q4_0",
    "--reasoning", "off",
    "--temp", "0.7", "--top-p", "0.80", "--top-k", "20", "--min-p", "0.0",
    "--presence-penalty", "1.5", "--frequency-penalty", "0.0", "--repeat-penalty", "1.0"]

PROMPTS = [
    ("code", "Write a Python quicksort with type hints. Output only the code, no explanation."),
    ("bash", "Write a bash one-liner that finds the ten largest files under /var. Output only the command."),
]

# (名字, inv, mc, rot_disable)
CASES = [
    ("E1-inv1-mc1-rot0", True,  True,  False),
    ("E2-inv0-mc1-rot0", False, True,  False),   # ★ 关键未知
    ("E3-inv1-mc0-rot1", True,  False, True),    # 旋转单独影响
    ("E4-inv1-mc0-rot0", True,  False, False),   # 无 mc 基线（应为 ~0.80）
]


def sh(a):
    r = subprocess.run(a, capture_output=True)
    return (r.stdout or b"").decode("utf-8", "replace").strip()


def vram():
    try:
        return sh(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader"]).split("\n")[0]
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


def probe(p, mx=220):
    body = json.dumps({"model": "bonsai", "messages": [{"role": "user", "content": p}],
                       "max_tokens": mx, "temperature": 0.2}).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    tm = d.get("timings", {}) or {}
    dn, da = tm.get("draft_n"), tm.get("draft_n_accepted")
    txt = d["choices"][0]["message"].get("content") or ""
    return {"dec": round(tm.get("predicted_per_second") or 0, 2),
            "acc": (round(da / dn, 3) if (dn and da is not None) else None),
            "tok": d["usage"]["completion_tokens"], "len": len(txt)}


kill()
print("=== inv x mean-center x rotation 交互诊断 ===", flush=True)
rows = []
for name, inv, mc, rot in CASES:
    print("\n########## %s  (inv=%s mc=%s rot_disable=%s) ##########" % (name, int(inv), int(mc), int(rot)), flush=True)
    kill(); time.sleep(3)
    env = dict(os.environ)
    env["PATH"] = BINDIR + os.pathsep + env["PATH"]
    if inv:
        env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    else:
        env.pop("GGML_CUDA_BATCH_INVARIANT", None)
    if rot:
        env["LLAMA_ATTN_ROT_DISABLE"] = "1"
    else:
        env.pop("LLAMA_ATTN_ROT_DISABLE", None)
    cmd = [BIN] + ARGS + (["--kv-mean-center", KVMC] if mc else [])
    logp = os.path.join(BASE, "ex_%s.log" % name)
    with open(logp, "wb") as lg:
        subprocess.Popen(cmd, stdout=lg, stderr=subprocess.STDOUT, env=env)
    ld = ready()
    if ld is None:
        print("  加载失败", flush=True); rows.append((name, "-", "-", "-", "LOADFAIL")); kill(); continue
    print("  加载 %.0fs  显存 %s MiB" % (ld, vram()), flush=True)
    try:
        decs, accs = [], []
        for tag, p in PROMPTS:
            r = probe(p)
            decs.append(r["dec"])
            if r["acc"] is not None:
                accs.append(r["acc"])
            print("  %-5s dec %6.2f t/s  acc=%-6s  %d tok / %d 字符"
                  % (tag, r["dec"], r["acc"], r["tok"], r["len"]), flush=True)
            time.sleep(0.5)
        avg = sum(decs) / len(decs)
        aa = ("%.3f" % (sum(accs) / len(accs))) if accs else "-"
        rows.append((name, "%.2f" % avg, aa, vram(), ""))
    except Exception as e:
        print("  异常 %r" % (e,), flush=True); rows.append((name, "ERR", "-", "-", str(e)[:30]))
    kill()

print("\n\n============ 交互诊断结果 ============", flush=True)
print("%-20s %-9s %-9s %-9s %s" % ("配置", "dec 均", "接收率", "显存", "备注"), flush=True)
for r in rows:
    print("%-20s %-9s %-9s %-9s %s" % r, flush=True)
