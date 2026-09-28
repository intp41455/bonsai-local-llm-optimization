# -*- coding: utf-8 -*-
"""补测：off 档取全文；medium / xhigh 各加一次重复样本（原测试 n=1，不足以定论）。"""
import json, time, urllib.request

BASE = "http://127.0.0.1:8081"
OUT = r"D:\Bonsai-demo\_effort_test2.json"

PROMPT = """请回答下面三道题。每题只给最终答案 + 一行理由，不要长篇分析。

1) 一个球拍和一个球一共 110 分，球拍比球贵 100 分，球多少钱？（单位：分）
2) 三位数 153、370、371、407 都等于自身各位数字的立方和。除此之外，三位数里还有没有别的？
3) 5x5 方格，从左下角走到右上角，每次只能向右或向上走一格，共有多少条最短路径？

输出格式：
1) 答案：
2) 答案：
3) 答案：
"""

# 正确答案：1) 5 分   2) 没有   3) 252 条
ARMS = [
    ("off",    {"enable_thinking": False}, "第1次"),
    ("medium", {"reasoning_effort": "medium"}, "第2次"),
    ("xhigh",  {"reasoning_effort": "xhigh"}, "第2次"),
]


def post(path, obj, timeout=2400):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ntok(s):
    if not s:
        return 0
    return len(post("/tokenize", {"content": s}, timeout=120).get("tokens", []))


out = []
for name, kw, tag in ARMS:
    row = {"arm": name, "kwargs": kw, "run": tag}
    try:
        t0 = time.time()
        d = post("/v1/chat/completions", {
            "model": "bonsai-2-27b",
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 4000,
            "chat_template_kwargs": kw,
        })
        row["wall_s"] = round(time.time() - t0, 1)
        m = d["choices"][0]["message"]
        rc = m.get("reasoning_content") or ""
        ct = m.get("content") or ""
        row.update({
            "finish": d["choices"][0].get("finish_reason"),
            "reason_tok": ntok(rc), "answer_tok": ntok(ct),
            "answer_full": ct, "reason_full": rc,
        })
    except Exception as e:
        row["error"] = repr(e)[:300]
    out.append(row)
    print("=" * 70, flush=True)
    print("档位 %s (%s)  墙钟 %ss  思考 %s tok  答案 %s tok" % (
        row.get("arm"), tag, row.get("wall_s"), row.get("reason_tok"),
        row.get("answer_tok")), flush=True)
    print("--- 答案全文 ---", flush=True)
    print(row.get("answer_full", row.get("error")), flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
print("\n[完成]", flush=True)
