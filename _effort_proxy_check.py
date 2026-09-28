# -*- coding: utf-8 -*-
"""验证代理的思考档位注入：默认走 medium；客户端显式指定时不被覆盖。"""
import json, os, sys, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
PROXY = "http://127.0.0.1:8080"
BASE = "http://127.0.0.1:8081"
PROMPT = "一件事要说明白。请算：5x5 方格从左下角走到右上角，每次只能向右或向上，共有多少条最短路径？只给答案和一行理由。"


def post(base, path, obj, timeout=1800):
    req = urllib.request.Request(
        base + path, data=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ntok(s):
    return 0 if not s else len(post(BASE, "/tokenize", {"content": s}, 120).get("tokens", []))


def run(tag, kwargs):
    body = {"model": "bonsai-2-27b", "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 4000}
    if kwargs is not None:
        body["chat_template_kwargs"] = kwargs
    t0 = time.time()
    try:
        d = post(PROXY, "/v1/chat/completions", body)
    except Exception as e:
        print("%-34s ERROR %r" % (tag, e))
        return
    m = d["choices"][0]["message"]
    rc = m.get("reasoning_content") or ""
    print("%-34s 墙钟 %5.1f s   思考 %4d tok   答案 %3d tok   答: %s" % (
        tag, time.time() - t0, ntok(rc), ntok(m.get("content") or ""),
        (m.get("content") or "").strip().replace("\n", " ")[:46]))


eff = r"D:\Bonsai-demo\capture\effort.txt"
print("capture/effort.txt =", repr(open(eff, encoding="utf-8").read() if os.path.exists(eff) else "(不存在)"))
print()
run("① 经代理，不指定（应走 medium）", None)
run("② 经代理，显式 xhigh（不应被覆盖）", {"reasoning_effort": "xhigh"})
run("③ 经代理，显式 low（不应被覆盖）", {"reasoning_effort": "low"})
