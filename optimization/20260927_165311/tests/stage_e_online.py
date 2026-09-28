# -*- coding: utf-8 -*-
r"""阶段 E 在线端到端验证。

用法:
    python stage_e_online.py big       # POST 真实抓包(289KB) 到 :8080，预期拒绝/告警
    python stage_e_online.py small     # POST 小请求，预期 200 且 budget_check 走便宜路径

只做本地测试，不杀任何进程。
"""
import http.client
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

PROXY = ("127.0.0.1", 8080)
CAP = r"D:\Bonsai-demo\capture\req_012_135949.json"
REQ_LOG = r"D:\Bonsai-demo\logs\requests.jsonl"

PROMPT_BIG = CAP
SMALL_BODY = {"model": "bonsai-2-27b",
              "messages": [{"role": "user", "content": "只回复两个字：收到"}],
              "stream": False, "max_tokens": 16}


def post(body_bytes, timeout=600):
    conn = http.client.HTTPConnection(PROXY[0], PROXY[1], timeout=timeout)
    t0 = time.monotonic()
    conn.request("POST", "/v1/chat/completions", body=body_bytes,
                 headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    data = r.read()
    dt = time.monotonic() - t0
    conn.close()
    return r.status, data, dt


def newest_record(after_ts=None):
    rec = None
    if not os.path.exists(REQ_LOG):
        return None
    with open(REQ_LOG, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
            except Exception:
                continue
            if after_ts is None or (o.get("start_at") or "") >= after_ts:
                rec = o
    return rec


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "big").strip().lower()
    print("== 阶段 E 在线验证：%s ==" % mode)
    if mode == "prefill":
        filler = ("这是一段用于测量预填充速度的填充文本，内容本身没有语义价值。" * 400)
        body = {"model": "bonsai-2-27b",
                "messages": [{"role": "user", "content": filler}],
                "stream": False, "max_tokens": 1}
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        print("请求体: 预填充探针  %d 字节" % len(raw))
    elif mode == "big":
        raw = open(PROMPT_BIG, "rb").read()
        print("请求体: %s  %d 字节" % (PROMPT_BIG, len(raw)))
    else:
        raw = json.dumps(SMALL_BODY, ensure_ascii=False).encode("utf-8")
        print("请求体: 小请求  %d 字节" % len(raw))

    t_mark = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    status, data, dt = post(raw)
    print("HTTP 状态: %s   用时 %.0f ms" % (status, dt * 1000))
    try:
        obj = json.loads(data.decode("utf-8", "ignore"))
        print("响应(节选): %s" % json.dumps(obj, ensure_ascii=False)[:900])
    except Exception:
        print("响应(节选): %s" % data[:900])

    for _ in range(20):
        rec = newest_record(t_mark)
        if rec:
            break
        time.sleep(0.3)
    if rec:
        print("\n-- requests.jsonl 最新记录 --")
        for k in ("request_id", "status", "error_type", "finish_reason",
                  "input_tokens_total", "completion_tokens", "wall_ms", "notes"):
            print("   %-20s %s" % (k, json.dumps(rec.get(k), ensure_ascii=False)))
        print("   %-20s %s" % ("budget_check",
                               json.dumps(rec.get("budget_check"), ensure_ascii=False)))
    else:
        print("\n!! 未取到新记录")
    return 0


if __name__ == "__main__":
    sys.exit(main())