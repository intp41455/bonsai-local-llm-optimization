"""量出 <available_skills> 块的真实字符/条目/描述长度，用于反解生效预算"""
import json, os, sys, glob

sys.stdout.reconfigure(encoding="utf-8")

caps = sorted(glob.glob(r"D:\Bonsai-demo\capture\req_*.json"), key=os.path.getmtime)
for p in caps:
    d = json.load(open(p, encoding="utf-8"))
    tools = {(t.get("function") or {}).get("name"): (t.get("function") or {}).get("description", "")
             for t in d.get("tools", [])}
    des = tools.get("Skill", "")
    i = des.find("<available_skills>")
    j = des.find("</available_skills>")
    if i < 0 or j < 0:
        print(os.path.basename(p), "-> 无清单块")
        continue
    blk = des[i:j + 19]
    ls = [l for l in blk.split("\n") if l.strip().startswith("- ")]

    # 逐条拆：  - name: desc (location: path)
    descs = []
    locs = []
    for l in ls:
        body = l.strip()[2:]
        if " (location: " in body:
            head, tail = body.split(" (location: ", 1)
            locs.append(tail.rstrip(")"))
        else:
            head = body
        if ": " in head:
            descs.append(head.split(": ", 1)[1])
        else:
            descs.append("")

    descs.sort(key=len)
    n = len(ls)
    print("=" * 74)
    print(os.path.basename(p))
    print("  条目数            :", n)
    print("  块字符            :", len(blk), " 条均 %.1f 字符" % (len(blk) / max(1, n)))
    print("  清单块 token(服务端) 见另外的分词测量")
    if descs:
        print("  描述长度 min/中位/max: %d / %d / %d" % (descs[0].__len__(), descs[n // 2].__len__(), descs[-1].__len__()))
        import statistics
        print("  描述长度 均值        : %.1f 字符" % statistics.mean(len(x) for x in descs))
        # 描述长度为 0 的条数（names-only 的标志）
        zero = sum(1 for x in descs if len(x) == 0)
        print("  描述为空(被砍)条数   :", zero)
        # 反解：accounted ≈ desc + name + source(4) + 90
        acct = 0
        for l, de in zip(ls, descs):
            nm = l.strip()[2:].split(": ", 1)[0].split(" (location")[0]
            acct += len(de) + len(nm) + 4 + 90
        print("  按源码 charsFor 口径估算 accounted 字符: %d   (预算默认常量 = 8000)" % acct)
    if locs:
        print("  location 路径总字符 : %d  (条均 %.0f)" % (sum(len(x) for x in locs), sum(len(x) for x in locs) / len(locs)))
    print("  前 2 条原文:")
    for l in ls[:2]:
        print("    " + repr(l[:190]))
    print()
