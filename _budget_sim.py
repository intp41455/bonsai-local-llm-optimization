"""离线复现 WorkBuddy 的技能清单预算算法，验证三种情形的真实字符收益。

算法（源码：codebuddy-lite-wb.mjs → ToolManager.truncateSkillsByCharBudget）：
  accounted(e) = len(desc_eff) + len(name) + len(source) + 90
  protected    = 非 user 来源（bundled/builtin/在 overrides 中）
  ey = floor((B - Σprotected - Σ_nonprot(len(name)+len(source)+90)) / n_nonprot)
  if ey < 20:  非 protected 的描述全部置空（names-only）
  else:        非 protected 描述硬裁到 ey；protected 保留自身上限(默认 300)

渲染：  "- {name}: {desc} (location: {path})\r\n"
其中 path 与印刷符号【不计入预算】，所以是「削不掉的净收益」。
"""
import json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")

BUDGET_DEFAULT = 30000
CAP_DEFAULT = 300
OVERHEAD = 90          # 源码里的固定 per-entry 开销
SOURCE_LEN = 4         # "user" / "bundled" 等近似长度
NAMES_ONLY_MIN = 20


def parse_entries(path):
    d = json.load(open(path, encoding="utf-8"))
    tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
             for t in d.get("tools", [])}
    des = tools.get("Skill", "")
    i, j = des.find("<available_skills>"), des.find("</available_skills>")
    blk = des[i:j + 19]
    out = []
    for line in blk.split("\n"):
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:]
        pth = ""
        m = re.search(r" \(location: (.*)\)$", body)
        if m:
            pth = m.group(1)
            body = body[:m.start()]
        name, _, desc = body.partition(": ")
        # 还原被 hardCap 加上的省略号（视为已裁）
        out.append({
            "name": name,
            "desc": desc.rstrip("\u2026"),
            "path": pth,
            "is_user": r"\.workbuddy\skills" in pth.replace("/", "\\"),
            "raw_len": len(desc),
        })
    return out


def simulate(entries, budget, label):
    n = len(entries)
    accounted_fixed = [len(e["name"]) + SOURCE_LEN + OVERHEAD for e in entries]
    prot = [e for e, fx in zip(entries, accounted_fixed) if not e["is_user"]]
    non = [e for e, fx in zip(entries, accounted_fixed) if e["is_user"]]

    def raw(e):      # protected 保留自身上限
        return min(e["raw_len"], CAP_DEFAULT)

    fixed_all = sum(len(e["name"]) + SOURCE_LEN + OVERHEAD for e in entries)
    # protected 的实际计入
    prot_cost = sum(raw(e) + len(e["name"]) + SOURCE_LEN + OVERHEAD for e in prot)
    non_fixed = sum(len(e["name"]) + SOURCE_LEN + OVERHEAD for e in non)

    if not non:
        ey = CAP_DEFAULT
    else:
        ey = int((budget - prot_cost - non_fixed) / len(non))

    if ey < NAMES_ONLY_MIN:
        mode = "names-only"
        eff = {id(e): (raw(e) if not e["is_user"] else 0) for e in entries}
    else:
        mode = "trimmed" if ey < CAP_DEFAULT else "none"
        eff = {id(e): (min(e["raw_len"], CAP_DEFAULT) if not e["is_user"]
                       else min(e["raw_len"], ey)) for e in entries}

    accounted = sum(eff[id(e)] + len(e["name"]) + SOURCE_LEN + OVERHEAD for e in entries)
    rendered = sum(len("- " + e["name"] + ": " + "x" * eff[id(e)]) + len(e["path"]) + 18
                   for e in entries)
    print("%-34s n=%-4d ey=%-5d %-10s accounted=%6d  rendered=%6d"
          % (label, n, ey, mode, accounted, rendered))
    return rendered, ey, mode


cap = r"D:\Bonsai-demo\capture\req_006_053121.json"
E = parse_entries(cap)
users = [e for e in E if e["is_user"]]
print("抓包条目: %d  其中 user 来源 %d  非 user %d" % (len(E), len(users), len(E) - len(users)))
print("实测块字符(含 <available_skills> 标签) = 31037")
print()

r0, ey0, m0 = simulate(E, BUDGET_DEFAULT, "① 现状 148 条 / 预算 30000")

# ② 再软关 61 条 user 技能（去掉路径最短之外的随机性：这里去掉“非保留”的 61 条，
#    用前 61 条短路径的 user 条目近似，路径长度影响很小）
by_path = sorted(users, key=lambda e: len(e["path"]))
removed = set(id(e) for e in by_path[:61])
E2 = [e for e in E if id(e) not in removed]
r2, ey2, m2 = simulate(E2, BUDGET_DEFAULT, "② 再软关 61 条 / 预算 30000")

# ③ 只降预算到 12000（slim 启动器的做法）
r3, ey3, m3 = simulate(E, 12000, "③ 148 条 / 预算 12000（slim）")

# ④ 只把预算提高到 45000（看反向）
r4, ey4, m4 = simulate(E, 45000, "④ 148 条 / 预算 45000")

CHAR2TOK = 3598 / 12596.0   # 用实测“路径 12596 字符 = 3598 token”得到的中文密度
print()
print("字数→token 换算密度 = %.4f tok/字符（由路径实测反推）" % CHAR2TOK)
print()
print("② 相对 ① 的净收益: %6d 字符  ≈ %5.0f token" % (r0 - r2, (r0 - r2) * CHAR2TOK))
print("③ 相对 ① 的净收益: %6d 字符  ≈ %5.0f token   <-- slim 启动器的真实收益" % (r0 - r3, (r0 - r3) * CHAR2TOK))
print("④ 相对 ① 的净收益: %6d 字符  ≈ %5.0f token" % (r0 - r4, (r0 - r4) * CHAR2TOK))
print()
longs = [e for e in E if e["raw_len"] >= 200]
print("描述 >=200 字符的条目: %d 条（其中 user 来源 %d 条）"
      % (len(longs), sum(1 for e in longs if e["is_user"])))
