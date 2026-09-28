# -*- coding: utf-8 -*-
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
pool = json.load(open(r"D:\Bonsai-demo\_inject_pool.json", encoding="utf-8"))
us = [r for r in pool if "\\.workbuddy\\skills\\" in (r.get("filePath") or "").replace("/", "\\").lower()]
print("可注入用户技能 共 %d" % len(us))
print()
for i, r in enumerate(us):
    print("%3d| %-44s | %s" % (i + 1, str(r.get("name"))[:44], r.get("overrideKey")))
