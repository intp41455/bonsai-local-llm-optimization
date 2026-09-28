# -*- coding: utf-8 -*-
"""把 capture/ 里的小请求（<20KB，我自己发的测试）改名成 small_*，避免被预热误选"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
CAP = r"D:\Bonsai-demo\capture"
TH = 20000

for fn in sorted(os.listdir(CAP)):
    if not fn.startswith("req_") or not fn.endswith(".json"):
        continue
    p = os.path.join(CAP, fn)
    sz = os.path.getsize(p)
    mark = "保留 req_*" if sz >= TH else "改名 small_*"
    print("%-28s %8d  -> %s" % (fn, sz, mark))
    if sz < TH:
        os.rename(p, os.path.join(CAP, "small_" + fn[4:]))

print()
print("改名后：")
for fn in sorted(os.listdir(CAP)):
    if fn.endswith(".json"):
        print("   %-32s %8d" % (fn, os.path.getsize(os.path.join(CAP, fn))))
