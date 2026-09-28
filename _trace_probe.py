# -*- coding: utf-8 -*-
"""解剖 WorkBuddy trace，找出它发给模型的真实请求结构。"""
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
T = r"C:\Users\intpj\.workbuddy\traces"

targets = [
    os.path.join(T, "24268", "trace_488bfa07cf2440c09130844465d43f9d.json"),
    os.path.join(T, "22796", "trace_a2d15052be874732a7856f6292279273.json"),
    os.path.join(T, "21232", "trace_0f40121a5ee5453c90e428256e195be7.json"),
]


def walk(o, path="", depth=0, out=None, maxd=4):
    if out is None:
        out = []
    if depth > maxd:
        return out
    if isinstance(o, dict):
        for k, v in o.items():
            p = "%s.%s" % (path, k)
            if isinstance(v, (dict, list)):
                out.append((p, type(v).__name__, len(v)))
                walk(v, p, depth + 1, out, maxd)
            else:
                s = str(v)
                out.append((p, type(v).__name__, len(s)))
    elif isinstance(o, list):
        for i, v in enumerate(o[:3]):
            walk(v, "%s[%d]" % (path, i), depth + 1, out, maxd)
    return out


for p in targets:
    if not os.path.exists(p):
        continue
    print("=" * 78)
    print(p.split("\\")[-1], "%.1f KB" % (os.path.getsize(p) / 1024))
    print("=" * 78)
    d = json.load(open(p, encoding="utf-8"))
    rows = walk(d)
    # 只打印"看起来像 prompt / messages / tools"的键
    key = [r for r in rows if any(s in r[0].lower() for s in
                                  ("message", "prompt", "tool", "system", "content",
                                   "model", "request", "input", "token", "usage"))]
    for r in key[:60]:
        print("   %-70s %-6s %s" % (r[0][:70], r[1], r[2]))
    print()
