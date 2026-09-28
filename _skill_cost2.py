# -*- coding: utf-8 -*-
"""用服务端分词器精确核算 Skill 工具描述的成本，并查漏网软关键的键格式。"""
import json, os, re, sys, glob, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UP = "http://127.0.0.1:8081"


def ntok(s):
    req = urllib.request.Request(UP + "/tokenize",
                                data=json.dumps({"content": s}).encode("utf-8"),
                                headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return len(json.loads(r.read().decode("utf-8"))["tokens"])


# ---- 抓包：Ground truth ----
d = json.load(open(r"D:\Bonsai-demo\capture\req_006_053121.json", encoding="utf-8"))
tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
         for t in d["tools"]}
des = tools["Skill"]
i, j = des.find("<available_skills>"), des.find("</available_skills>")
blk = des[i:j + 19]
entries = []
for l in blk.split("\n"):
    l = l.strip()
    if l.startswith("- "):
        m = re.match(r"^- ([^:：]+)[:：]", l)
        if m:
            entries.append((m.group(1).strip(), l))

print("=== 抓包实测（post-trim）===")
print("清单条目数        :", len(entries))
print("清单块字符        :", len(blk))
print("清单块 token      :", ntok(blk))
print("Skill 描述 token  :", ntok(des))
print("ToolSearch  token :", ntok(tools.get("ToolSearch", "")))
tot = 0
for t in d["tools"]:
    tot += ntok(json.dumps(t, ensure_ascii=False))
print("全部 tools token  :", tot)
print("prompt_n 实测     :", 57885)

# 路径开销
pathc = sum(len(re.search(r"\(location: ([^)]*)\)", l).group(1)) for _, l in entries
           if re.search(r"\(location: ([^)]*)\)", l))
print("其中路径字符      :", pathc, " → token", ntok("x" * 0 + blk[:0] + "\\".join(
      [re.search(r"\(location: ([^)]*)\)", l).group(1) for _, l in entries
       if re.search(r"\(location: ([^)]*)\)", l)])))

# 每条平均
avg_c = len(blk) / max(1, len(entries))
print("平均每条字符      : %.1f" % avg_c)

# ---- 增量：被摘除的 61 条代价（按同分布估）----
baks = sorted(glob.glob(r"C:\Users\intpj\.workbuddy\settings.json.bak-trim2-*"),
              key=os.path.getmtime)
new = json.load(open(r"C:\Users\intpj\.workbuddy\settings.json", encoding="utf-8"))["skillOverrides"]
old = json.load(open(baks[-1], encoding="utf-8"))["skillOverrides"]
added = sorted(set(new) - set(old))
print()
print("=== 本轮摘除 ===")
print("新增软关键数      :", len(added))
print("→ 按同分布估算摘除 token: %d 条 × %.0f tok/条 ≈ %d tok"
      % (len(added), ntok(blk) / max(1, len(entries)), len(added) * ntok(blk) / max(1, len(entries))))
print("参考：prompt 57,885 → 占比 %.1f%%"
      % (100.0 * len(added) * ntok(blk) / max(1, len(entries)) / 57885))

# ---- 漏网键格式 ----
print()
print("=== 11 条漏网技能在 settings 里的键 ===")
targets = ["deep-research", "find-skills", "neodata-financial-search", "pdf", "pdfkit-py",
           "playwright-cli", "weixinpay-feedback", "weixinpay-pay", "weixinpay-register",
           "westock-data", "westock-tool"]
for t in targets:
    ks = [k for k in new if k == t or k.startswith(t + "@")
          or k.replace("\\", "/").rstrip("/").endswith("/" + t)]
    print("  %-26s -> %s" % (t, ks if ks else "(无键)"))
