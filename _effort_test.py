# -*- coding: utf-8 -*-
"""实测 reasoning_effort 四档：思考 token 量、耗时、答案正确性。
用服务端 /tokenize 精确数 token，不用字符估算。
"""
import json, time, urllib.request, sys

BASE = "http://127.0.0.1:8081"
OUT = r"D:\Bonsai-demo\_effort_test.json"

PROMPT = """请回答下面三道题。每题只给最终答案 + 一行理由，不要长篇分析。

1) 一个球拍和一个球一共 110 分，球拍比球贵 100 分，球多少钱？（单位：分）
2) 三位数 153、370、371、407 都等于自身各位数字的立方和。除此之外，三位数里还有没有别的？
3) 5x5 方格，从左下角走到右上角，每次只能向右或向上走一格，共有多少条最短路径？

输出格式：
1) 答案：
2) 答案：
3) 答案：
"""

ARMS = [
    ("off",    {"enable_thinking": False}),
    ("low",    {"reasoning_effort": "low"}),
    ("medium", {"reasoning_effort": "medium"}),
    ("xhigh",  {"reasoning_effort": "xhigh"}),
]
MAXTOK = 4000


def post(path, obj, timeout=2400):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ntok(s):
    if not s:
        return 0
    try:
        return len(post("/tokenize", {"content": s}, timeout=120).get("tokens", []))
    except Exception as e:
        return -1


results = []
for name, kw in ARMS:
    row = {"arm": name, "kwargs": kw}
    try:
        t0 = time.time()
        d = post("/v1/chat/completions", {
            "model": "bonsai-2-27b",
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": MAXTOK,
            "chat_template_kwargs": kw,
        })
        wall = time.time() - t0
        ch = d["choices"][0]
        m = ch["message"]
        rc = m.get("reasoning_content") or ""
        ct = m.get("content") or ""
        tm = d.get("timings", {})
        row.update({
            "wall_s": round(wall, 1),
            "msg_keys": sorted(m.keys()),
            "finish": ch.get("finish_reason"),
            "reason_tok": ntok(rc),
            "answer_tok": ntok(ct),
            "reason_chars": len(rc),
            "answer_chars": len(ct),
            "prompt_n": tm.get("prompt_n"),
            "predicted_n": tm.get("predicted_n"),
            "decode_tps": round(tm.get("predicted_per_second") or 0, 2),
            "reason_head": rc.strip()[:260],
            "answer": ct.strip()[:500],
            "content_raw_head": ct.strip()[:200] if not rc else "",
        })
    except Exception as e:
        row["error"] = repr(e)[:400]
    results.append(row)
    print(json.dumps(row, ensure_ascii=False, indent=1), flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

print("\n================ 汇总 ================", flush=True)
print("%-8s %8s %8s %9s %9s %9s %s" % ("档位", "墙钟s", "解码t/s", "思考tok", "答案tok", "总tok", "finish"), flush=True)
for r in results:
    if "error" in r:
        print("%-8s  ERROR: %s" % (r["arm"], r["error"]), flush=True)
        continue
    print("%-8s %8.1f %8.2f %9d %9d %9d %s" % (
        r["arm"], r["wall_s"], r["decode_tps"], r["reason_tok"],
        r["answer_tok"], r["reason_tok"] + r["answer_tok"], r["finish"]), flush=True)
