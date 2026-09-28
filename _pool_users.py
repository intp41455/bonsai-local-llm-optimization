# -*- coding: utf-8 -*-
"""列出 101 条可注入用户技能，标注是否有真实使用记录，用于定保留白名单。"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
WB = r"C:\Users\intpj\.workbuddy"

pool = json.load(open(r"D:\Bonsai-demo\_inject_pool.json", encoding="utf-8"))
users = [r for r in pool if "\\.workbuddy\\skills\\" in (r.get("filePath") or "").replace("/", "\\").lower()]

usage = json.load(open(os.path.join(WB, "usage-log.json"), encoding="utf-8"))
sk = usage.get("skills") or {}


def used(name, key):
    for k in (name, key):
        if k and k in sk:
            return sk[k]
    return None


print("可注入用户技能: %d" % len(users))
print()
rows = []
for r in users:
    u = used(r.get("name"), r.get("overrideKey"))
    rows.append((r.get("name") or "", r.get("overrideKey") or "", u, r.get("filePath") or ""))

hit = [r for r in rows if r[2] is not None]
nohit = [r for r in rows if r[2] is None]
print("=== 有真实使用记录（%d）===" % len(hit))
for n, k, u, _ in sorted(hit, key=lambda x: -(x[2] if isinstance(x[2], (int, float)) else 0)):
    print("   %-42s %-38s uses=%s" % (n[:42], k[:38], u))
print()
print("=== 从未使用（%d）===" % len(nohit))
for i in range(0, len(nohit), 2):
    print("   " + " | ".join("%-42s" % r[0][:42] for r in nohit[i:i + 2]))
print()
print("--- usage-log.skills 顶层键数: %d ---" % len(sk))
print("--- 键样例:", list(sk.keys())[:12])
