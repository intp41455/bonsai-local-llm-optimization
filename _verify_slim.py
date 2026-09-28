# -*- coding: utf-8 -*-
"""验证三项叠加瘦身效果"""
import importlib.util
import json

spec = importlib.util.spec_from_file_location("bp", r"D:/Bonsai-demo/proxy/bonsai_proxy.py")
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)

raw = open("capture/req_004_122147.json", "rb").read()
out, saved = bp.strip_locations(raw)
print("原始字节:", len(raw))
print("瘦身后  :", len(out))
print("剥离字符:", saved)

out2, saved2 = bp.strip_locations(out)
print("幂等性  :", "OK" if saved2 == 0 else "FAIL(saved2=%d)" % saved2)

out3, _ = bp.strip_locations(raw)
print("确定性  :", "OK" if out3 == out else "FAIL")

d = json.loads(out.decode("utf-8"))
for name in ["Skill", "ToolSearch", "Agent"]:
    t = [t for t in d["tools"] if t["function"]["name"] == name][0]
    desc = t["function"]["description"]
    print("%-12s: desc_len=%6d  has_location=%s  has_deferred=%s  has_subagent=%s" % (
        name, len(desc),
        "(location:" in desc,
        "available_deferred" in desc and len(desc) > 200,
        "subagent" in desc.lower() and len(desc) > 200))
