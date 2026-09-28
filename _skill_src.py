# -*- coding: utf-8 -*-
"""按来源拆解 Skill 工具 description 里的 <available_skills> 清单。"""
import json, re, os, glob, sys, collections

sys.stdout.reconfigure(encoding="utf-8")

CAP = r"D:\Bonsai-demo\capture"
cands = sorted(glob.glob(os.path.join(CAP, "req_*.json")), key=os.path.getmtime)
if not cands:
    print("!! capture/ 下没有 req_*.json")
    sys.exit(1)
p = cands[-1]
print("样本:", os.path.basename(p))

d = json.load(open(p, encoding="utf-8"))
tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
         for t in d.get("tools", [])}
des = tools.get("Skill", "")
i, j = des.find("<available_skills>"), des.find("</available_skills>")
if i < 0 or j < 0:
    print("!! 未找到 <available_skills> 块")
    sys.exit(1)
blk = des[i:j + 19]
lines = [l for l in blk.split("\n") if l.strip().startswith("- ")]
print("available_skills 条目数:", len(lines))

src = collections.Counter()
for l in lines:
    m = re.search(r"\(location: ([^)]*)\)", l)
    pth = (m.group(1) if m else "").replace("/", "\\").lower()
    if "\\plugins\\" in pth:
        mm = re.search(r"\\plugins\\([^\\]+)\\([^\\]+)", pth)
        src["插件: " + (mm.group(2) if mm else "?")] += 1
    elif "\\.workbuddy\\skills\\" in pth:
        src["用户技能"] += 1
    else:
        src["其他: " + (pth[:50] or "无路径")] += 1

print()
for k, v in src.most_common():
    print("  %-44s %3d" % (k, v))

pathc = sum(len(re.search(r"\(location: ([^)]*)\)", l).group(1))
            for l in lines if re.search(r"\(location: ([^)]*)\)", l))
print()
print("块字符      :", len(blk), " ≈%d tok" % (len(blk) / 3.5))
print("其中路径字符:", pathc, " ≈%d tok" % (pathc / 3.5))
print("Skill 描述  :", len(des), " ≈%d tok" % (len(des) / 3.5))
