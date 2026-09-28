# -*- coding: utf-8 -*-
"""对撞：本次新增软关的键 vs 抓包实际注入清单。"""
import json, re, os, glob, sys, difflib, time

sys.stdout.reconfigure(encoding="utf-8")

SET = r"C:\Users\intpj\.workbuddy\settings.json"
baks = sorted(glob.glob(r"C:\Users\intpj\.workbuddy\settings.json.bak-trim2-*"),
              key=os.path.getmtime)
print("trim2 备份:", [os.path.basename(b) for b in baks])
if not baks:
    sys.exit("!! 没有 trim2 备份，无法求差集")

new = json.load(open(SET, encoding="utf-8")).get("skillOverrides") or {}
old = json.load(open(baks[-1], encoding="utf-8")).get("skillOverrides") or {}
added = sorted(set(new) - set(old))
print("本次新增软关键数:", len(added))

cands = sorted(glob.glob(r"D:\Bonsai-demo\capture\req_*.json"), key=os.path.getmtime)
d = json.load(open(cands[-1], encoding="utf-8"))
tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
         for t in d.get("tools", [])}
des = tools.get("Skill", "")
i, j = des.find("<available_skills>"), des.find("</available_skills>")
blk = des[i:j + 19]
names = []
for l in blk.split("\n"):
    l = l.strip()
    if l.startswith("- "):
        m = re.match(r"^- ([^:：]+)[:：]", l)
        if m:
            names.append(m.group(1).strip())
print("抓包清单条目数:", len(names), " (样本", os.path.basename(cands[-1]), ")")

nset = set(names)
leaked = [k for k in added if k in nset]
print()
print(">> 新增软关的 61 条里，仍出现在抓包清单的:", len(leaked))
if leaked:
    for k in leaked:
        print("     ", k)
else:
    print("     (无 —— 全部成功摘除)")

# 反向：抓包清单里，有多少条现在标着 user-invocable-only
alloff = {k for k, v in new.items() if v == "user-invocable-only"}
still = sorted(nset & alloff)
print()
print(">> 抓包清单 148 条中仍标 user-invocable-only 的:", len(still))
for k in still:
    print("     ", k)
