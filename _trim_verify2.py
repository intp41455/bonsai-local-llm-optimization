# -*- coding: utf-8 -*-
"""核对：被标 'user-invocable-only' 的技能，是否真从 <available_skills> 消失。"""
import json, re, os, glob, sys, time, collections

sys.stdout.reconfigure(encoding="utf-8")

SETTINGS = r"C:\Users\intpj\.workbuddy\settings.json"
CAP = r"D:\Bonsai-demo\capture"

cfg = json.load(open(SETTINGS, encoding="utf-8"))
so = cfg.get("skillOverrides") or {}
vc = collections.Counter(so.values())
print("skillOverrides 取值分布:", dict(vc))
off = {k for k, v in so.items() if v == "user-invocable-only"}
print("被软关（user-invocable-only）:", len(off))

cands = sorted(glob.glob(os.path.join(CAP, "req_*.json")), key=os.path.getmtime)
for p in cands:
    d = json.load(open(p, encoding="utf-8"))
    tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
             for t in d.get("tools", [])}
    des = tools.get("Skill", "")
    i, j = des.find("<available_skills>"), des.find("</available_skills>")
    if i < 0:
        print("\n%-26s (无 Skill 工具 / 非对话请求)" % os.path.basename(p))
        continue
    blk = des[i:j + 19]
    lines = [l.strip() for l in blk.split("\n") if l.strip().startswith("- ")]
    names = []
    for l in lines:
        m = re.match(r"^- ([^:：]+)[:：]", l)
        if m:
            names.append(m.group(1).strip())
    still = sorted(set(names) & off)
    print("\n%-26s  mtime=%s" % (os.path.basename(p),
          time.strftime("%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p)))))
    print("   清单条目=%d   其中被软关的=%d   块字符=%d" % (len(names), len(still), len(blk)))
    if still:
        print("   例:", ", ".join(still[:8]))
