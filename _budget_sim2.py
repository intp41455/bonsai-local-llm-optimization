"""用服务端 /tokenize 精确量三种技能清单方案的真实 token 数。

关键：抓包里的描述【已被裁过】（hardCap 加了省略号），所以还原"自然长度"
必须回 .skill-list-cache.json 取原始 description 文本，否则 ey 变化的影响会算错。
"""
import json, re, sys, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UP = "http://127.0.0.1:8081"
CAP = r"D:\Bonsai-demo\capture\req_006_053121.json"
CACHE = r"C:\Users\intpj\.workbuddy\.skill-list-cache.json"

BUDGET, CAP_DESC, OVERHEAD, SRC = 30000, 300, 90, 4
NAMES_ONLY_MIN = 20
USER_RE = re.compile(r"\.workbuddy\s*[\\/]\s*skills", re.I)


def post(path, obj, timeout=300):
    req = urllib.request.Request(UP + path, data=json.dumps(obj).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ntok(s):
    return len(post("/tokenize", {"content": s})["tokens"])


# ---------------- 抓包里的真实渲染文本 ----------------
d = json.load(open(CAP, encoding="utf-8"))
tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
         for t in d.get("tools", [])}
des = tools["Skill"]
i, j = des.find("<available_skills>"), des.find("</available_skills>")
blk = des[i:j + 19]

entries = []
for line in blk.split("\n"):
    line = line.rstrip("\r").strip()
    if not line.startswith("- "):
        continue
    body = line[2:]
    m = re.search(r" \(location: (.*)\)$", body)
    pth = m.group(1) if m else ""
    if m:
        body = body[:m.start()]
    name, _, desc = body.partition(": ")
    entries.append({"name": name, "desc": desc.rstrip("\u2026"), "path": pth})

# ---------------- 自然描述文本（清单缓存） ----------------
nat = {}
try:
    raw = json.load(open(CACHE, encoding="utf-8"))
    pool = raw.get("results") or raw.get("skills") or []
    if isinstance(pool, dict):
        pool = list(pool.values())
    for it in pool:
        if not isinstance(it, dict):
            continue
        nm = it.get("name") or it.get("skillName")
        dsc = it.get("description") or ""
        if nm and dsc:
            nat.setdefault(nm, re.sub(r"\s+", " ", dsc).strip())
    print("清单缓存自然描述: %d 条" % len(nat))
except Exception as e:
    print("清单缓存读取失败:", e)

hits = [e for e in entries if e["name"] in nat]
cut = [e for e in hits if len(nat[e["name"]]) > len(e["desc"]) + 1]
print("抓包 %d 条，命中自然描述 %d 条；其中被裁过的 %d 条" % (len(entries), len(hits), len(cut)))
if cut:
    print("  被裁前平均 %.0f 字符 → 抓包里 %.0f 字符"
          % (sum(len(nat[e["name"]]) for e in cut) / len(cut),
             sum(len(e["desc"]) for e in cut) / len(cut)))
print("实测基准：抓包原块 %d 字符 / %d token" % (len(blk), ntok(blk)))
print()


def natlen(e):
    return max(len(e["desc"]), len(nat.get(e["name"], "")))


def simulate(ents, budget, label):
    for e in ents:
        e["is_user"] = bool(USER_RE.search(e["path"]))
    prot = [e for e in ents if not e["is_user"]]
    non = [e for e in ents if e["is_user"]]

    prot_cost = sum(min(natlen(e), CAP_DESC) + len(e["name"]) + SRC + OVERHEAD for e in prot)
    non_fixed = sum(len(e["name"]) + SRC + OVERHEAD for e in non)
    ey = CAP_DESC if not non else int((budget - prot_cost - non_fixed) / len(non))

    eff = {}
    for e in ents:
        cap = CAP_DESC if not e["is_user"] else ey
        if cap < NAMES_ONLY_MIN:
            eff[e["name"]] = ""
        else:
            text = nat.get(e["name"]) or e["desc"]
            eff[e["name"]] = text[:min(len(text), cap)]

    lines = ["<available_skills>"]
    for e in ents:
        lines.append("- %s: %s (location: %s)" % (e["name"], eff[e["name"]], e["path"]))
    lines.append("</available_skills>")
    block = "\n".join(lines)
    tk = ntok(block)
    mode = "names-only" if ey < NAMES_ONLY_MIN else ("trimmed" if ey < CAP_DESC else "none")
    print("%-30s n=%-4d ey=%-5s %-10s 字符=%6d  token=%6d"
          % (label, len(ents), ey, mode, len(block), tk))
    return len(block), tk


c0, t0 = simulate(entries, BUDGET, "① 现状 / 预算 30000")

users = [e for e in entries if USER_RE.search(e["path"])]
drop = {id(e) for e in sorted(users, key=lambda e: len(e["path"]))[:61]}
e2 = [e for e in entries if id(e) not in drop]
c2, t2 = simulate(e2, BUDGET, "② 再软关 61 条 user 技能")

c3, t3 = simulate(entries, 12000, "③ 只降预算到 12000")
c4, t4 = simulate(entries, 45000, "④ 只升预算到 45000")

print()
print("② 相对 ① 净省 : %6d 字符 / %5d token   (每条 %.0f token)"
      % (c0 - c2, t0 - t2, (t0 - t2) / 61.0))
print("③ 相对 ① 净省 : %6d 字符 / %5d token   <-- slim 启动器的真实收益"
      % (c0 - c3, t0 - t3))
print("④ 相对 ① 净省 : %6d 字符 / %5d token" % (c0 - c4, t0 - t4))
print()
print("prompt 总量参照 57,885 token；抓包原块 %d token = 占 %.1f%%" % (t0, 100.0 * t0 / 57885))
