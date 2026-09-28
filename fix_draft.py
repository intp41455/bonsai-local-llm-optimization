#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""定位 MTP 接受率崩坏的真因：怀疑 draft 的 KV 类型不能量化（draft 不继承 mean-center 偏置）。

变量矩阵（全部带 --kv-mean-center，c32768，K=1，reasoning=off）：
  D1  -ctkd f16 -ctvd f16   draft KV 全精度
  D2  (不给 ctkd/ctvd)       走默认
  D3  -ctkd q4_0 -ctvd q4_0  现状（对照，已知 ~0.17）
  D4  -ctkd q8_0 -ctvd q8_0  draft KV 半精度
同时抓服务日志中 KV 类型确认参数是否真正落地。
"""
import json, os, re, subprocess, time, urllib.request

BASE = r"D:\Bonsai-demo"
BINDIR = os.path.join(BASE, "dist", "bonsai2-8gb", "bin")
BIN = os.path.join(BINDIR, "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")
KVMC = os.path.join(M27, "kv-mean-center.gguf")
os.environ["no_proxy"] = "127.0.0.1"; os.environ["NO_PROXY"] = "127.0.0.1"

K1 = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]
COMMON = ["--host", "127.0.0.1", "--port", "8080", "-a", "bonsai",
          "-fa", "on", "-np", "1", "--cache-ram", "0", "--jinja",
          "--kv-mean-center", KVMC,
          "--reasoning", "off",
          "--temp", "0.7", "--top-p", "0.80", "--top-k", "20", "--min-p", "0.0",
          "--presence-penalty", "1.5", "--frequency-penalty", "0.0", "--repeat-penalty", "1.0"]

PROMPTS = [
    ("code", "Write a Python quicksort with type hints. Output only the code, no explanation."),
    ("bash", "Write a bash one-liner that finds the ten largest files under /var. Output only the command."),
]

CASES = [
    ("D1-draftKV-f16", ["-ctkd", "f16", "-ctvd", "f16"]),
    ("D2-draftKV-default", []),
    ("D3-draftKV-q4_0", ["-ctkd", "q4_0", "-ctvd", "q4_0"]),
    ("D4-draftKV-q8_0", ["-ctkd", "q8_0", "-ctvd", "q8_0"]),
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
            "pre": round(tm.get("prompt_per_second") or 0, 1),
            "acc": (round(da / dn, 3) if (dn and da is not None) else None),
            "tok": d["usage"]["completion_tokens"], "len": len(txt)}


def kvtypes(logpath):
    """从服务日志抓 KV cache 类型行，确认参数是否真正落地。"""
    try:
        raw = open(logpath, "rb").read().decode("utf-8", "replace")
    except Exception:
        return "-"
    hits = re.findall(r"(?:type_k|type_v|KV cache|kv cache)[^\n]{0,90}", raw)
    return " | ".join(h.strip() for h in hits[:4]) if hits else "-"


env = dict(os.environ)
env["PATH"] = BINDIR + os.pathsep + env["PATH"]
env["GGML_CUDA_BATCH_INVARIANT"] = "1"

kill()
print("=== draft KV 类型诊断（全部带 --kv-mean-center, c32768, K=1）===", flush=True)
rows = []
for name, kvargs in CASES:
    print("\n########## %s ##########" % name, flush=True)
    kill(); time.sleep(3)
    logp = os.path.join(BASE, "dx_%s.log" % name)
    with open(logp, "wb") as lg:
        subprocess.Popen([BIN, "-m", LEAN, "-ngl", "99", "-c", "32768"] + K1 + kvargs + COMMON,
                         stdout=lg, stderr=subprocess.STDOUT, env=env)
    if ready() is None:
        print("  加载失败", flush=True); rows.append((name, "-", "-", "-", "LOADFAIL")); kill(); continue
    print("  显存 %s MiB  KV: %s" % (vram(), kvtypes(logp)[:110]), flush=True)
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

print("\n\n============ draft KV 类型诊断结果 ============", flush=True)
print("%-22s %-9s %-9s %-9s %s" % ("配置", "dec 均", "接收率", "显存", "备注"), flush=True)
for r in rows:
    print("%-22s %-9s %-9s %-9s %s" % r, flush=True)
