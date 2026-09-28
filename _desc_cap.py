# -*- coding: utf-8 -*-
"""量出默认描述截断长度、是否触发总量截断，并提取相关常量。"""
import json, re, sys

sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"D:\Bonsai-demo\capture\req_006_053121.json", encoding="utf-8"))
tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
         for t in d["tools"]}
des = tools["Skill"]

print("=== 截断提示注释 ===")
for pat in ["due to token limits", "trimmed to fit token limits",
            "More skills are available in these directories", "<skills_overview>"]:
    print("  %-46s %s" % (pat, pat in des))

blk = des[des.find("<available_skills>"):des.find("</available_skills>") + 19]
descs = []
for l in blk.split("\n"):
    l = l.strip()
    m = re.match(r"^- ([^:：]+)[:：] (.*)$", l)
    if not m:
        continue
    body = m.group(2)
    body = body[:body.rfind(" (location:")] if " (location:" in body else body
    descs.append((m.group(1), body))
print()
print("条目:", len(descs))
lens = sorted(len(b) for _, b in descs)
import collections
print("描述长度 min/中位/max:", lens[0], lens[len(lens)//2], lens[-1])
print("以 … 结尾的条数    :", sum(1 for _, b in descs if b.endswith("\u2026")))
print()
print("最长的 5 条:")
for n, b in sorted(descs, key=lambda x: -len(x[1]))[:5]:
    print("  %-40s %4d  %s" % (n[:40], len(b), b[-30:]))
print()
print("长度直方图（每 20 字符一档，只显示靠右的尾部）:")
c = collections.Counter(len(b)//20*20 for _, b in descs)
for k in sorted(c)[-8:]:
    print("  %4d-%4d : %s" % (k, k+19, "#"*c[k]))
print()
print("=== 尾部 400 字符（看是否有 overview 注释）===")
print(des[-400:].replace("\r", ""))
