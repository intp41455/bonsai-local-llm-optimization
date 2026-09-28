# -*- coding: utf-8 -*-
"""
技能池二次收窄：101 -> 40（软关 61 条）。

依据（三条硬数据，不是拍脑袋）：
  1. usage-log.json：这 101 条里只有 13 条有真实使用记录（87% 从未用过）
  2. 可注入池 124 条里，121 条是 WorkBuddy 每次请求都带的固定开销
     （实测每条 ≈ 121 token，占整个 55k prompt 的约 43%）
  3. WorkBuddy 对技能清单有展示上限（表现为 "Showing 200 of N"），
     所以只有把池子压到 200 以下才真正省 token

软关 = 写入 settings.json 的 skillOverrides，值 "user-invocable-only"
     = 不再自动注入 prompt，但 SKILL.md 原封不动、/技能名 仍可手动调用。
     完全可逆：删掉对应键即可。

用法: python _sk_trim2.py            # 干跑
      python _sk_trim2.py --apply    # 落盘
"""
import json
import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

DRY = "--apply" not in sys.argv
WB = r"C:\Users\intpj\.workbuddy"
SP = os.path.join(WB, "settings.json")

# ---------------- 保留清单（40 条，按用途分组） ----------------
KEEP = {
    # —— 模型部署 / 调参（当前主线项目）——
    "ternary-gguf-8gb-deploy",
    "workbuddy-prompt-slimming",
    "llamacpp-vram-tuning",
    "private-ai-deploy",
    "byom-config",
    "free-api-wiring",
    "token-efficient-task-router",
    "omniroute__skillhub",
    # —— 办公 / 文档（usage-log 里最高频的一类）——
    "html-to-pdf",
    "html2pdf",
    "doc-format-validator",
    "docx-format-clone",
    "word-formatter__skillhub",
    "document-processing-system",
    "doc-compare",
    "办公高效技能",
    "xlsx",
    "excel-pro",
    "zagens-office",
    # —— 开发 / 交付 ——
    "github",
    "fullstack-dev",
    "browser-e2e-static-site",
    "shipping-and-launch",
    "edgeone-pages-deploy",
    "github-workflow",
    # —— 写作 / 审校 ——
    "ai-text-humanizer",
    "self-correction",
    "long-text-writer",
    # —— 平台元技能（Agent 自身选型 / 造技能要用）——
    "make-skill",
    "super-skill-helper",
    "skill-discovery-index",
    "skill-project-dev-docs",
    "using-agent-skills",
    # —— 腾讯生态 ——
    "smart-page",
    "ima-skill",
    "lexiang-knowledge-base",
    # —— 数据 / 媒体 ——
    "chart-visualization",
    "data-insight-analyst",
    "cn-ocr",
    # —— 演示 ——
    "ppt-design",
}

pool = json.load(open(r"D:\Bonsai-demo\_inject_pool.json", encoding="utf-8"))
us = [r for r in pool
      if "\\.workbuddy\\skills\\" in (r.get("filePath") or "").replace("/", "\\").lower()]
print("可注入用户技能 :", len(us))

bykey = {r.get("overrideKey"): r for r in us}
missing = [k for k in KEEP if k not in bykey]
print("保留清单在池内找不到的:", len(missing), missing)

keep = [r for r in us if r.get("overrideKey") in KEEP]
drop = [r for r in us if r.get("overrideKey") not in KEEP]
print("保留 %d  |  软关 %d" % (len(keep), len(drop)))

# 每条技能描述的真实字符量（用于估算 token）
kc = sum(len((r.get("name") or "") + (r.get("description") or "")) for r in keep)
dc = sum(len((r.get("name") or "") + (r.get("description") or "")) for r in drop)
tot = kc + dc
print()
print("描述字符量: 保留 %d / 软关 %d / 合计 %d" % (kc, dc, tot))
print("按实测每条约 121 token 估算: 软关 %.0f 条 = 约 %d token"
      % (len(drop), len(drop) * 121))

S = json.load(open(SP, encoding="utf-8"))
so = S.setdefault("skillOverrides", {})
print()
print("现有 skillOverrides :", len(so))
newkeys = [r["overrideKey"] for r in drop if r.get("overrideKey")]
add = [k for k in newkeys if k not in so]
print("将新增             :", len(add), "（已存在跳过 %d）" % (len(newkeys) - len(add)))
print("写入后             :", len(so) + len(add))

# 冲突检查：保留项的键绝不能被写进去
clash = [k for k in KEEP if k in so and so[k] == "user-invocable-only"]
print("保留项里面已被关掉的:", len(clash), clash)

if DRY:
    print()
    print("*** DRY RUN —— 未写入。加 --apply 执行。***")
    print()
    print("保留清单（%d）:" % len(keep))
    for r in sorted(keep, key=lambda x: x.get("overrideKey") or ""):
        print("   %-42s %s" % (str(r.get("name"))[:42], r.get("overrideKey")))
    sys.exit(0)

ts = time.strftime("%Y%m%d-%H%M%S")
bak = SP + ".bak-trim2-" + ts
shutil.copy2(SP, bak)
print("\n已备份:", os.path.basename(bak))
for k in add:
    so[k] = "user-invocable-only"
with open(SP, "w", encoding="utf-8", newline="\n") as f:
    json.dump(S, f, ensure_ascii=False, indent=2)

# 复验
S2 = json.load(open(SP, encoding="utf-8"))
assert isinstance(S2.get("skillOverrides"), dict)
print("已写入。skillOverrides 现有 %d 条。JSON 合法 OK。" % len(S2["skillOverrides"]))
print("顶层键保持一致:", list(S2.keys()) == list(S.keys()))
