#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MTP 投机解码配置扫描（RTX 5060 Laptop 8GB / PTQ1_0）
策略：每个配置 -> 启动 -> 记录显存 -> 双探针(code/prose) -> 记录 decode/prefill/接收率 -> 关闭
自带悬崖检测：decode < 5 t/s 判为越界（WDDM 换页），该方向不再加码。
"""
import json, os, subprocess, sys, time, urllib.request

BASE = r"D:\Bonsai-demo"
BIN = os.path.join(BASE, "bin", "cuda", "llama-server.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
PTQ = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0.gguf")
MTP_FAT = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp.gguf")
MTP_LEAN = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf")

os.environ["no_proxy"] = "127.0.0.1"
os.environ["NO_PROXY"] = "127.0.0.1"

P_CODE = "Write a Python quicksort with type hints. Output only the code."
P_PROSE = "In two short paragraphs, explain why the sky appears blue to a curious ten year old."

SPEC_ON = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1"]

CONFIGS = [
    ("L16-OFF", MTP_LEAN, ["-ngl", "99", "-c", "16384"]),
    ("L16-MTP1", MTP_LEAN, ["-ngl", "99", "-c", "16384"] + SPEC_ON),
    ("L24-MTP1", MTP_LEAN, ["-ngl", "99", "-c", "24576"] + SPEC_ON),
    ("L32-MTP1", MTP_LEAN, ["-ngl", "99", "-c", "32768"] + SPEC_ON),
    ("L32-UB128", MTP_LEAN, ["-ngl", "99", "-c", "32768", "-b", "512", "-ub", "128"] + SPEC_ON),
    ("F16-MTP1", MTP_FAT, ["-ngl", "99", "-c", "16384"] + SPEC_ON),
]

COMMON = [
    "--host", "127.0.0.1", "--port", "8080", "-a", "bonsai",
    "-fa", "on", "-np", "1", "--cache-ram", "0",
    "--jinja", "--reasoning-effort", "low",
    "-ctk", "q4_0", "-ctv", "q4_0", "-ctkd", "q4_0", "-ctvd", "q4_0",
    "--backend-sampling",
    "--temp", "1.0", "--top-p", "0.95", "--top-k", "20", "--min-p", "0.05",
]


def sh(args):
    r = subprocess.run(args, capture_output=True)
    return (r.stdout or b"").decode("utf-8", errors="replace").strip()


def vram():
    out = sh(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"])
    return out.split("\n")[0] if out else "?"


def alive(timeout=2):
    try:
        urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=timeout).read()
        return True
    except Exception:
        return False


def kill():
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    for _ in range(45):
        time.sleep(1)
        if not alive():
            time.sleep(2)
            if not alive():
                return True
    return False


def ready(timeout=420):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5)
            if json.loads(r.read()).get("status") == "ok":
                return time.time() - t0
        except Exception:
            pass
        time.sleep(3)
    return None


def probe(prompt, max_tokens=200):
    body = json.dumps({"model": "bonsai", "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": 1.0, "top_p": 0.95}).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=3600).read())
    tm = d.get("timings", {}) or {}
    return {
        "wall": round(time.time() - t0, 2),
        "tok": d["usage"]["completion_tokens"],
        "dec": round(tm.get("predicted_per_second") or 0.0, 2),
        "pre": round(tm.get("prompt_per_second") or 0.0, 1),
        "dn": tm.get("draft_n"), "da": tm.get("draft_n_accepted"),
    }


def acc(r):
    if r.get("dn") and r.get("da") is not None and r["dn"]:
        try:
            return round(float(r["da"]) / float(r["dn"]), 3)
        except Exception:
            return None
    return None


env = dict(os.environ)
env["PATH"] = os.path.join(BASE, "bin", "cuda") + os.pathsep + env["PATH"]
env["BONSAI_KV4"] = "1"

rows = []
kill()
print("=== GPU 起始: %s ===" % vram(), flush=True)

for name, model, extra in CONFIGS:
    print("\n########## %s ##########" % name, flush=True)
    if not os.path.exists(model):
        print("  模型缺失，跳过: %s" % os.path.basename(model), flush=True)
        rows.append((name, "-", "-", "-", "-", "MISSING")); continue
    kill(); time.sleep(3)
    logp = os.path.join(BASE, "sweep_%s.log" % name.split()[0])
    cmd = [BIN, "-m", model] + extra + COMMON
    with open(logp, "wb") as lg:
        p = subprocess.Popen(cmd, stdout=lg, stderr=subprocess.STDOUT, env=env)
    ld = ready()
    if ld is None:
        print("  加载失败/超时", flush=True)
        rows.append((name, "-", "-", "-", "-", "LOADFAIL"))
        kill(); continue
    used = vram()
    print("  加载 %.0fs  显存 %s" % (ld, used), flush=True)
    try:
        rc = probe(P_CODE); time.sleep(1)
        rp = probe(P_PROSE)
        cliff = max(rc["dec"], rp["dec"]) < 5.0
        print("  code : dec %6.2f t/s  pre %6.1f t/s  tok=%3d  draft=%s/%s acc=%s"
              % (rc["dec"], rc["pre"], rc["tok"], rc["da"], rc["dn"], acc(rc)), flush=True)
        print("  prose: dec %6.2f t/s  pre %6.1f t/s  tok=%3d  draft=%s/%s acc=%s"
              % (rp["dec"], rp["pre"], rp["tok"], rp["da"], rp["dn"], acc(rp)), flush=True)
        if cliff:
            print("  >>> 越崖（WDDM 换页）<<<", flush=True)
        best = max(rc["dec"], rp["dec"])
        rows.append((name, used, "%.2f" % best, "%.1f" % max(rc["pre"], rp["pre"]),
                     "%s/%s" % (acc(rc), acc(rp)), "CLIFF" if cliff else "ok"))
    except Exception as e:
        print("  探针异常: %r" % (e,), flush=True)
        rows.append((name, used, "ERR", "ERR", "-", str(e)[:40]))
    kill()

print("\n\n================ 汇总 ================", flush=True)
print("%-30s %-14s %-10s %-11s %-14s %s" % ("配置", "显存", "dec t/s", "pre t/s", "接收率", "状态"), flush=True)
for r in rows:
    print("%-30s %-14s %-10s %-11s %-14s %s" % r, flush=True)
