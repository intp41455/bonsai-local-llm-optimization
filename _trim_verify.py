# -*- coding: utf-8 -*-
"""核对：settings.json 里被软关的技能，是否真的从 <available_skills> 消失了。"""
import json, re, os, glob, sys

sys.stdout.reconfigure(encoding="utf-8")

SETTINGS = r"C:\Users\intpj\.workbuddy\settings.json"
CACHE = r"C:\Users\intpj\.workbuddy\.skill-list-cache.json"
CAP = r"D:\Bonsai-demo\capture"

cfg = json.load(open(SETTINGS, encoding="utf-8"))
so = cfg.get("skillOverrides") or {}
off = {k: v for k, v in so.items() if v is False or v == 0 or v == "" }
print("settings.json skillOverrides 总数 :", len(so))
print("其中被软关（falsy）            :", len(off))

# 抓包里的技能名
cands = sorted(glob.glob(os.path.join(CAP, "req_*.json")), key=os.path.getmtime)
d = json.load(open(cands[-1], encoding="utf-8"))
tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
         for t in d.get("tools", [])}
des = tools.get("Skill", "")
i, j = des.find("<available_skills>"), des.find("</available_skills>")
blk = des[i:j + 19]
lines = [l.strip() for l in blk.split("\n") if l.strip().startswith("- ")]

capskills = []
for l in lines:
    m = re.search(r"^- `?([^`\s]+)`?", l)
    if m:
        capskills.append(m.group(1))
print("抓包技能条目数                 :", len(capskills))
print("样本:", os.path.basename(cands[-1]))

cset = set(capskills)
# 被软关的键 -> 取技能名部分（overrideKey 形如 name@source 或 路径型）
hit = []
for k in off:
    name = k.split("@")[0].split("\\")[-1].split("/")[-1]
    if name in cset:
        hit.append(name)
print()
print(">> 被软关但仍出现在抓包清单里的:", len(hit))
for n in sorted(hit)[:20]:
    print("     ", n)

print()
print("=== .skill-list-cache.json ===")
if os.path.exists(CACHE):
    print("mtime:", __import__("time").strftime("%Y-%m-%d %H:%M:%S",
          __import__("time").localtime(os.path.getmtime(CACHE))))
    c = json.load(open(CACHE, encoding="utf-8"))
    if isinstance(c, dict):
        print("顶层键:", list(c.keys())[:10])
        for kk in c:
            vv = c[kk]
            if isinstance(vv, list):
                print("  %s: list(%d)" % (kk, len(vv)))
            elif isinstance(vv, dict):
                print("  %s: dict(%d)" % (kk, len(vv)))
    elif isinstance(c, list):
        print("list(%d)" % len(c))
        print("首项:", json.dumps(c[0], ensure_ascii=False)[:300] if c else "-")
else:
    print("(不存在)")
