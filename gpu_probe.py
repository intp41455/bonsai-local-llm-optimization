#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""负载下同步采样 GPU 频率/功耗，判断是否被墙。"""
import os, subprocess, sys, threading, time

BIN = r"D:\Bonsai-demo\dist\bonsai2-8gb\bin\llama-bench.exe"
BINDIR = os.path.dirname(BIN)
MODEL = r"D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0.gguf"

env = dict(os.environ)
env["PATH"] = BINDIR + os.pathsep + env["PATH"]

samples = []
stop = False


def sampler():
    while not stop:
        r = subprocess.run(["nvidia-smi",
                            "--query-gpu=clocks.current.graphics,clocks.current.memory,power.draw,"
                            "temperature.gpu,utilization.gpu,pstate,clocks_event_reasons.sw_power_cap",
                            "--format=csv,noheader"], capture_output=True)
        t = (r.stdout or b"").decode("utf-8", "replace").strip()
        if t:
            samples.append(t)
        time.sleep(0.7)


th = threading.Thread(target=sampler, daemon=True)
th.start()

print("=== 启动 llama-bench（tg 长跑）===", flush=True)
p = subprocess.run([BIN, "-m", MODEL, "-ngl", "99", "-fa", "1", "-ctk", "q4_0", "-ctv", "q4_0",
                    "-p", "512", "-n", "512", "-r", "5", "-d", "0"],
                   env=env, capture_output=True, timeout=1200)
stop = True
time.sleep(1)
out = ((p.stdout or b"") + (p.stderr or b"")).decode("utf-8", "replace")
for ln in out.strip().splitlines():
    if "t/s" in ln or "|" in ln:
        print("   " + ln, flush=True)

print("\n=== GPU 采样（%d 个点）===" % len(samples), flush=True)
print("  %-9s %-9s %-8s %-5s %-5s %-5s %s" % ("graphics", "memory", "power", "temp", "util", "pst", "sw_power_cap"))
for s in samples[::3][:26]:
    print("  " + s)

import statistics as st
def col(i):
    v = []
    for s in samples:
        try:
            v.append(float(s.split(",")[i].strip().split()[0]))
        except Exception:
            pass
    return v

for name, i, unit in [("graphics MHz", 0, ""), ("memory MHz", 1, ""), ("power W", 2, "")]:
    c = col(i)
    if c:
        print("\n  %s: min %.0f / 中位 %.0f / max %.0f %s" % (name, min(c), st.median(c), max(c), unit))
