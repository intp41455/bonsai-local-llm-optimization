# -*- coding: utf-8 -*-
"""精确列出当前会被注入的技能（读 .skill-list-cache.json），并按来源分组。"""
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
WB = r"C:\Users\intpj\.workbuddy"

p = os.path.join(WB, ".skill-list-cache.json")
d = json.load(open(p, encoding="utf-8"))
res = d["results"] if isinstance(d, dict) else d
print("缓存条目总数 :", len(res))

inj = [r for r in res if not r.get("disable") and not r.get("disableModelInvocation")]
print("当前会被注入 :", len(inj))
print("被 disable   :", sum(1 for r in res if r.get("disable")))
print("user-inv-only:", sum(1 for r in res if r.get("disableModelInvocation")))
print()

# 字段
print("单条字段:", sorted(inj[0].keys()) if inj else "(空)")
print()


def source(r):
    fp = (r.get("filePath") or r.get("path") or "").replace("/", "\\").lower()
    if "\\.workbuddy\\skills\\" in fp:
        return "user-skills"
    if "app.asar.unpacked\\resources\\plugins" in fp:
        return "app-builtin"
    if "\\.workbuddy\\plugins\\" in fp:
        return "plugin-cache"
    return "other"


c = Counter(source(r) for r in inj)
print("=== 注入池来源分布 ===")
for k, v in c.most_common():
    print("  %-16s %4d" % (k, v))
print()

for tag in ("app-builtin", "plugin-cache", "other"):
    sub = [r for r in inj if source(r) == tag]
    if not sub:
        continue
    print("=== %s（%d 条）— 不受 skillOverrides 控制 ===" % (tag, len(sub)))
    for r in sorted(sub, key=lambda x: (x.get("name") or "")):
        print("   %-46s %s" % (str(r.get("name"))[:46],
                               os.path.basename(os.path.dirname((r.get("filePath") or "").replace("/", "\\")))))
    print()

# user-skills 的 overrideKey 是否都在 settings 里
S = json.load(open(os.path.join(WB, "settings.json"), encoding="utf-8"))
so = S.get("skillOverrides") or {}
us = [r for r in inj if source(r) == "user-skills"]
miss = [r for r in us if r.get("overrideKey") not in so]
print("=== user-skills 注入池 %d 条；其中 overrideKey 不在 settings 的 %d 条 ==="
      % (len(us), len(miss)))
for r in miss[:40]:
    print("   %-46s key=%s" % (str(r.get("name"))[:46], r.get("overrideKey")))
print()

json.dump([{k: r.get(k) for k in ("name", "overrideKey", "filePath", "disable",
                                 "disableModelInvocation")} for r in inj],
          open(r"D:\Bonsai-demo\_inject_pool.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("明细 -> _inject_pool.json")
