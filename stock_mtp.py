#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 stock 二进制上用 recipe 的黄金参数实测 MTP（对照自编版）。"""
import json, os, subprocess, time, urllib.request

BASE = r"D:\Bonsai-demo"
BIN = os.path.join(BASE, "bin", "cuda", "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")
KVMC = os.path.join(M27, "kv-mean-center.gguf")

os.environ["no_proxy"] = "127.0.0.1"; os.environ["NO_PROXY"] = "127.0.0.1"

P_CODE = "Write a Python quicksort with type hints. Output only the code, no explanation."
P_PROSE = "In two short paragraphs, explain why the sky appears blue to a curious ten year old."


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
    return {"wall": round(time.time() - t0, 1), "tok": d["usage"]["completion_tokens"],
            "dec": round(tm.get("predicted_per_second") or 0, 2),
            "pre": round(tm.get("prompt_per_second") or 0, 1),
            "acc": (round(da / dn, 3) if (dn and da is not None) else None)}


COMMON = ["--host", "127.0.0.1", "--port", "8080", "-a", "bonsai",
          "-fa", "on", "-np", "1", "--cache-ram", "0", "--jinja",
          "--reasoning-effort", "low", "--reasoning-budget", "4096",
          "-ctk", "q4_0", "-ctv", "q4_0", "-ctkd", "q4_0", "-ctvd", "q4_0",
          "--temp", "0.7", "--top-p", "0.80", "--top-k", "20",
          "--presence-penalty", "1.5", "--frequency-penalty", "0.0", "--repeat-penalty", "1.0"]

CONFIGS = [
    ("C32K-K1", ["-ngl", "99", "-c", "32768", "--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]),
    ("C32K-K2", ["-ngl", "99", "-c", "32768", "--spec-type", "draft-mtp", "--spec-draft-n-max", "2"]),
    ("C32K-OFF", ["-ngl", "99", "-c", "32768"]),
]

env = dict(os.environ)
env["PATH"] = os.path.join(BASE, "bin", "cuda") + os.pathsep + env["PATH"]
env["GGML_CUDA_BATCH_INVARIANT"] = "1"

kill()
print("=== GPU 起始 %s ===" % vram(), flush=True)
rows = []
for name, extra in CONFIGS:
    print("\n########## %s ##########" % name, flush=True)
    kill(); time.sleep(3)
    cmd = [BIN, "-m", LEAN] + extra + COMMON
    with open(os.path.join(BASE, "stock_%s.log" % name), "wb") as lg:
        subprocess.Popen(cmd, stdout=lg, stderr=subprocess.STDOUT, env=env)
    ld = ready()
    if ld is None:
        print("  加载失败", flush=True); rows.append((name, "-", "-", "-", "-", "LOADFAIL")); kill(); continue
    print("  加载 %.0fs  显存 %s" % (ld, vram()), flush=True)
    try:
        rc = probe(P_CODE); time.sleep(1); rp = probe(P_PROSE)
        print("  code : dec %6.2f t/s  pre %6.1f t/s  tok=%4d  acc=%s" % (rc["dec"], rc["pre"], rc["tok"], rc["acc"]), flush=True)
        print("  prose: dec %6.2f t/s  pre %6.1f t/s  tok=%4d  acc=%s" % (rp["dec"], rp["pre"], rp["tok"], rp["acc"]), flush=True)
        rows.append((name, vram() or "-", "%.2f" % max(rc["dec"], rp["dec"]), "%.1f" % max(rc["pre"], rp["pre"]),
                     "%s/%s" % (rc["acc"], rp["acc"]), "CLIFF" if max(rc["dec"], rp["dec"]) < 5 else "ok"))
    except Exception as e:
        print("  探针异常 %r" % (e,), flush=True)
        rows.append((name, vram() or "-", "ERR", "ERR", "-", str(e)[:36]))
    kill()

print("\n============ stock 版汇总 ============", flush=True)
print("%-12s %-14s %-10s %-11s %-16s %s" % ("配置", "显存", "dec", "pre", "接收率", "状态"), flush=True)
for r in rows:
    print("%-12s %-14s %-10s %-11s %-16s %s" % r, flush=True)
