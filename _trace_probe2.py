# -*- coding: utf-8 -*-
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
T = r"C:\Users\intpj\.workbuddy\traces"

p = os.path.join(T, "24268", "trace_488bfa07cf2440c09130844465d43f9d.json")
d = json.load(open(p, encoding="utf-8"))
print("顶层键:", list(d.keys()))
for k, v in d.items():
    if isinstance(v, dict):
        print("  %s -> dict keys: %s" % (k, list(v.keys())))
    elif isinstance(v, list):
        print("  %s -> list len %d" % (k, len(v)))
        if v and isinstance(v[0], dict):
            print("      [0] keys:", list(v[0].keys()))
    else:
        print("  %s -> %r" % (k, v))

print()
tr = d.get("trace") or {}
print("trace 全字段:")
for k, v in tr.items():
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    print("   %-26s %s" % (k, s[:160]))

print()
sp = d.get("spans") or []
print("spans 数:", len(sp))
for i, s in enumerate(sp[:6]):
    print("   --- span[%d] keys: %s" % (i, list(s.keys())))
    for k in ("name", "type", "startTime", "endTime", "model", "durationMs",
              "inputTokens", "outputTokens", "totalTokens", "status"):
        if k in s:
            print("        %-14s %s" % (k, json.dumps(s[k], ensure_ascii=False)[:200]))
    ti = s.get("toolInput")
    if ti:
        print("        toolInput 前 300:", str(ti)[:300].replace("\n", " "))
