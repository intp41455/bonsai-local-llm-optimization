# -*- coding: utf-8 -*-
"""查这 11 条"已标软关却仍在清单"的技能，究竟来自哪儿。"""
import json, re, os, sys

sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"D:\Bonsai-demo\capture\req_006_053121.json", encoding="utf-8"))
tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
         for t in d["tools"]}
des = tools["Skill"]
blk = des[des.find("<available_skills>"):des.find("</available_skills>") + 19]

targets = ["deep-research", "find-skills", "neodata-financial-search", "pdf", "pdfkit-py",
           "playwright-cli", "weixinpay-feedback", "weixinpay-pay", "weixinpay-register",
           "westock-data", "westock-tool"]
print("%-26s %-9s %s" % ("条目名", "来源", "location"))
print("-" * 100)
for l in blk.split("\n"):
    l = l.strip()
    m = re.match(r"^- ([^:：]+)[:：]", l)
    if not m:
        continue
    nm = m.group(1).strip()
    if nm not in targets:
        continue
    loc = re.search(r"\(location: ([^)]*)\)", l)
    p = (loc.group(1) if loc else "").replace("/", "\\")
    kind = "插件" if "\\plugins\\" in p.lower() else ("用户" if "\\.workbuddy\\skills\\" in p.lower() else "其他")
    print("%-26s %-9s %s" % (nm, kind, p[:70]))
