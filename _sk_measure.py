# -*- coding: utf-8 -*-
"""用真实 description 实测技能收窄的 token 收益（数据源：.skill-list-cache.json）。"""
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
PORT = 8081
WB = r"C:\Users\intpj\.workbuddy"

KEEP = {
    "ternary-gguf-8gb-deploy", "workbuddy-prompt-slimming", "llamacpp-vram-tuning",
    "private-ai-deploy", "byom-config", "free-api-wiring",
    "token-efficient-task-router", "omniroute__skillhub",
    "html-to-pdf", "html2pdf", "doc-format-validator", "docx-format-clone",
    "word-formatter__skillhub", "document-processing-system", "doc-compare",
    "办公高效技能", "xlsx", "excel-pro", "zagens-office",
    "github", "fullstack-dev", "browser-e2e-static-site",
    "shipping-and-launch", "edgeone-pages-deploy", "github-workflow",
    "ai-text-humanizer", "self-correction", "long-text-writer",
    "make-skill", "super-skill-helper", "skill-discovery-index",
    "skill-project-dev-docs", "using-agent-skills",
    "smart-page", "ima-skill", "lexiang-knowledge-base",
    "chart-visualization", "data-insight-analyst", "cn-ocr", "ppt-design",
}

_op = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ntok(t):
    req = urllib.request.Request("http://127.0.0.1:%d/tokenize" % PORT,
                                 data=json.dumps({"content": t}).encode(),
                                 headers={"Content-Type": "application/json"})
    r = json.load(_op.open(req, timeout=180))
    tk = r.get("tokens")
    return len(tk) if isinstance(tk, list) else int(tk)


cache = json.load(open(os.path.join(WB, ".skill-list-cache.json"), encoding="utf-8"))
res = cache["results"] if isinstance(cache, dict) else cache
inj = [r for r in res if not r.get("disable") and not r.get("disableModelInvocation")]

def src(r):
    fp = (r.get("filePath") or "").replace("/", "\\").lower()
    if "\\.workbuddy\\skills\\" in fp:
        return "user"
    if "app.asar.unpacked\\resources\\plugins" in fp:
        return "builtin"
    if "\\.workbuddy\\plugins\\" in fp:
        return "plugincache"
    return "other"

users = [r for r in inj if src(r) == "user"]
others = [r for r in inj if src(r) != "user"]

keep = [r for r in users if r.get("overrideKey") in KEEP]
drop = [r for r in users if r.get("overrideKey") not in KEEP]


def line(r):
    d = (r.get("description") or "").replace("\n", " ")
    return "- %s: %s\n" % (r.get("name"), d)


def total(rs):
    return sum(len(line(r)) for r in rs)


def tk(rs):
    return ntok("".join(line(r) for r in rs))


print("当前可注入池 : %d 条（user %d / 非 user %d）" % (len(inj), len(users), len(others)))
print()
for tag, rs in (("user 保留", keep), ("user 软关", drop), ("非 user（不可控）", others)):
    print("%-18s %3d 条  %7d 字符  %6d token" % (tag, len(rs), total(rs), tk(rs)))
print()
print("收窄前 user 段 : %6d token" % tk(users))
print("收窄后 user 段 : %6d token" % tk(keep))
print("=> 省下        : %6d token（约占 55,273 的 %.1f%%）"
      % (tk(drop), tk(drop) / 55273 * 100))
print("=> 平均每条    : %6.0f token" % (tk(drop) / max(1, len(drop))))
