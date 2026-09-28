# -*- coding: utf-8 -*-
"""阶段 C 验收测试（离线；纯“模拟 SSE 上游”，不加载第二个模型进程）

覆盖方案 §5 / §C5 清单：
  C1 首块立即转发（不等待攒满固定大小）、字节不丢不重复
  C1 增量 SSE 解析：拆块 / UTF-8 跨块 / CRLF / 注释心跳 / 多事件同块 /
                    [DONE] / reasoning_content / content / tool 参数增量
  C1 4xx-5xx 与非流式响应完整转发、中途断流被记录
  C2 三档超时：first_response / no_data(stream idle) / overall
  C2 客户端取消 -> 记录 client_disconnected，并验证后端 /slots 释放
  C3 单槽串行化：并发请求排队，queue_ms 可观测，上游同时只被一个请求占用
  C4 requests.jsonl 字段齐全；复用分档替代旧的 prompt_n<1500 绝对判据
  C5 不加载第二个模型进程（全部走本地 mock）

用法：
    python stage_c_tests.py                      # 测已部署的 D:\Bonsai-demo\proxy\bonsai_proxy.py
    set BONSAI_PROXY_PATH=<待测文件> && python stage_c_tests.py   # 测暂存副本（部署前）
"""
import http.client
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

PROXY = os.environ.get("BONSAI_PROXY_PATH") or r"D:\Bonsai-demo\proxy\bonsai_proxy.py"

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  <- " + str(detail)) if (detail and not cond) else ""))


# ================================================================ 模拟上游
EV_ROLE = b'data: {"model":"bonsai-2-27b","choices":[{"delta":{"role":"assistant"}}]}\n\n'


def exact_chunks():
    """一份含各种“脏”情况的 SSE 流（方案 §C1 要求逐项覆盖）。"""
    parts = [EV_ROLE]                                        # 普通事件
    parts.append(b": ping\n\n")                              # 注释心跳（LF）
    parts.append(b'data: {"choices":[{"delta":{"reasoning_content":"\xe5\x85\x88\xe6\x83\xb3\xe4\xb8\x89\xe6\xad\xa5"}}]}\r\n\r\n')
    parts.append(b'data: {"choices":[{"delta":{"reasoning_content":"\xe5\x9b\x9b\xe6\xad\xa5\xef\xbc\x81"}}]}\r\n\r\n')  # CRLF
    txt = 'data: {"choices":[{"delta":{"content":"\u7b54\u6848\u2705\u597d"}}]}\n\n'
    raw = txt.encode("utf-8")
    i = raw.index("\u2705".encode("utf-8")) + 1              # 切在多字节字符中间
    parts.append(raw[:i])
    parts.append(raw[i:])
    parts.append(b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
                 b'"function":{"name":"x","arguments":"{\\"a\\""}}]}}]}\n\n'
                 b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,'
                 b'"function":{"arguments":":1}"}}]}}]}\n\n')   # 两条事件同一块
    parts.append(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}],'
                 b'"usage":{"prompt_tokens":1234,"completion_tokens":56,'
                 b'"completion_tokens_details":{"reasoning_tokens":0}},'
                 b'"timings":{"prompt_n":52,"cache_n":60409,"prompt_ms":120.0,'
                 b'"predicted_n":56,"predicted_per_second":19.5},"stop_type":"eos"}\n\n')
    parts.append(b"data: [DONE]\n\n")
    return parts


BIG = b'data: {"choices":[{"delta":{"content":"' + b"x" * 200000 + b'"}}]}\n\n'


class Mock(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    lock = threading.Lock()
    inflight = 0
    max_inflight = 0

    def log_message(self, fmt, *a):
        pass

    def _json(self, code, obj):
        msg = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
        except Exception:
            pass

    def _stream_headers(self):
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()

    def _write(self, data):
        try:
            self.wfile.write(data)
            self.wfile.flush()
            return True
        except Exception:
            return False

    def do_GET(self):
        with Mock.lock:
            busy = Mock.inflight > 0
        if self.path.startswith("/slots"):
            self._json(200, [{"is_processing": busy, "n_prompt_tokens": 0}])
        elif self.path.startswith("/health"):
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        with Mock.lock:
            Mock.inflight += 1
            Mock.max_inflight = max(Mock.max_inflight, Mock.inflight)
        try:
            ln = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(ln) if ln else b"{}"
            try:
                req = json.loads(raw.decode("utf-8", "ignore"))
            except Exception:
                req = {}
            beh = (req or {}).get("mock_behavior") or "immediate"
            if beh == "immediate":
                self._stream_headers()
                self._write(EV_ROLE)
                time.sleep(0.6)
                self._write(b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n')
                self._write(b"data: [DONE]\n\n")
            elif beh == "exact":
                self._stream_headers()
                for c in exact_chunks():
                    if not self._write(c):
                        return
            elif beh == "error500":
                self._json(500, {"error": {"message": "boom"}})
            elif beh == "broken":
                self._stream_headers()
                self._write(EV_ROLE)
                self._write(b'data: {"choices":[{"delta":{"content":"\xe6\x96\xad')
            elif beh == "slow_first":
                time.sleep(0.8)
                self._stream_headers()
                self._write(EV_ROLE)
                self._write(b"data: [DONE]\n\n")
            elif beh == "stall":
                self._stream_headers()
                self._write(EV_ROLE)
                time.sleep(1.5)
                self._write(b"data: [DONE]\n\n")
            elif beh == "dribble":
                # 一直有小块数据（永不触发“无数据超时”），用于触发 overall 上限
                self._stream_headers()
                self._write(EV_ROLE)
                for _ in range(5):
                    time.sleep(0.2)
                    if not self._write(b'data: {"choices":[{"delta":{"content":"."}}]}\n\n'):
                        return
                self._write(b"data: [DONE]\n\n")
            elif beh == "cancel":
                self._stream_headers()
                self._write(EV_ROLE)
                time.sleep(0.3)
                self._write(BIG)
            else:
                self._json(400, {"error": "unknown behavior"})
        finally:
            with Mock.lock:
                Mock.inflight -= 1


# ================================================================ 工具
def load_proxy():
    spec = importlib.util.spec_from_file_location("px_stage_c", PROXY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def post(proxy_port, behavior, stream=True, wait_all=True):
    body = json.dumps({"model": "bonsai-2-27b",
                       "messages": [{"role": "user", "content": "hi"}],
                       "stream": stream, "mock_behavior": behavior}).encode("utf-8")
    conn = http.client.HTTPConnection("127.0.0.1", proxy_port, timeout=30)
    t0 = time.monotonic()
    conn.request("POST", "/v1/chat/completions", body=body,
                 headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    first = r.read1(4096)
    ttfb = time.monotonic() - t0
    data = first
    if wait_all:
        while True:
            c = r.read1(65536)
            if not c:
                break
            data += c
    total = time.monotonic() - t0
    status = r.status
    conn.close()
    return {"status": status, "body": data, "ttfb": ttfb, "total": total}


def read_records(path):
    out = []
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    return out


def wait_record(path, pred, timeout=8.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        for r in read_records(path):
            if pred(r):
                return r
        time.sleep(0.2)
    return None


def main():
    print("== 阶段 C 验收测试 ==")
    print("   被测代理: %s" % PROXY)
    tmp = tempfile.mkdtemp(prefix="bonsai_stage_c_")
    P = load_proxy()

    mock = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=mock.serve_forever, daemon=True).start()
    mport = mock.server_address[1]

    P.CFG["capture_dir"] = tmp
    P.CFG["request_log"] = os.path.join(tmp, "requests.jsonl")
    P.ARGS = SimpleNamespace(effort=None, keep_location=True, upstream=mport,
                             port=0, config=None)
    # 阶段一：常规超时（不触发超时）
    P.CFG["timeouts"].update({"connect_s": 2, "first_response_s": 5,
                              "stream_idle_s": 5, "overall_s": 30,
                              "client_write_s": 1,
                              "release_wait_s": 2})

    srv = ThreadingHTTPServer(("127.0.0.1", 0), P.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    pport = srv.server_address[1]
    log = P.CFG["request_log"]

    # ---------------- C1: 首块立即转发 + 字节不丢不重复 ----------------
    r = post(pport, "immediate")
    want = (EV_ROLE + b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
            + b"data: [DONE]\n\n")
    check("C1 首块立即转发（TTFB<0.35s，不等攒满）", r["ttfb"] < 0.35,
          "ttfb=%.3fs" % r["ttfb"])
    check("C1 整段耗时 >=0.55s（说明确实是边收边转，不是缓冲到结束）",
          r["total"] >= 0.55, "total=%.3fs" % r["total"])
    check("C1 字节不丢不重复（客户端收到的 == 上游发出的）", r["body"] == want,
          "len=%d/%d" % (len(r["body"]), len(want)))

    # ---------------- C1: 增量解析（脏数据全覆盖）----------------
    r2 = post(pport, "exact")
    parts = exact_chunks()
    check("C1 脏 SSE 流字节完全一致（拆块/CRLF/心跳/多事件同块/UTF-8 跨块）",
          r2["body"] == b"".join(parts),
          "len=%d/%d" % (len(r2["body"]), len(b"".join(parts))))
    rec = wait_record(log, lambda x: x.get("est_reasoning_chars") == 7)
    rec = rec or {}
    check("C1 解析出 reasoning 字数=7", rec.get("est_reasoning_chars") == 7,
          rec.get("est_reasoning_chars"))
    check("C1 解析出 content 字数=4（含 emoji，UTF-8 跨块未破）",
          rec.get("est_answer_chars") == 4, rec.get("est_answer_chars"))
    check("C1 解析出 tool 参数增量字数=7", rec.get("est_tool_arg_chars") == 7,
          rec.get("est_tool_arg_chars"))
    check("C1 解析出 tool_calls 增量条数=2", rec.get("tool_calls") == 2,
          rec.get("tool_calls"))
    check("C1 注释心跳被识别", (rec.get("sse_heartbeats") or 0) >= 1,
          rec.get("sse_heartbeats"))
    check("C1 finish_reason / stop_type 正确", rec.get("finish_reason") == "stop"
          and rec.get("stop_type") == "eos",
          "%s/%s" % (rec.get("finish_reason"), rec.get("stop_type")))
    check("C1 服务端 timings 采用（pn=52 高比例复用）",
          rec.get("prompt_evaluated_tokens") == 52
          and rec.get("cache_reused_tokens") == 60409
          and rec.get("cache_reuse") == "高比例复用",
          "%s/%s/%s" % (rec.get("prompt_evaluated_tokens"),
                        rec.get("cache_reused_tokens"), rec.get("cache_reuse")))
    check("C1 usage 采用（input=1234 completion=56）",
          rec.get("input_tokens_total") == 1234 and rec.get("completion_tokens") == 56,
          "%s/%s" % (rec.get("input_tokens_total"), rec.get("completion_tokens")))
    check("C1 reasoning_tokens=0 时记 null 并加说明（不判“没思考”）",
          rec.get("reasoning_tokens") is None
          and any("reasoning_tokens" in n for n in (rec.get("notes") or [])),
          rec.get("reasoning_tokens"))
    check("C1 truncated=False（finish=stop）", rec.get("truncated") is False,
          rec.get("truncated"))

    # ---------------- C1: 错误响应 / 非流式 / 断流 ----------------
    r3 = post(pport, "error500", stream=False)
    check("C1 上游 500 原样转发（状态码+响应体完整）",
          r3["status"] == 500 and json.loads(r3["body"].decode())["error"]["message"] == "boom",
          "%s %r" % (r3["status"], r3["body"][:80]))
    r4 = post(pport, "broken")
    check("C1 中途断流：已生成的片段被保留转发",
          r4["body"].startswith(EV_ROLE) and b"[DONE]" not in r4["body"],
          len(r4["body"]))
    rec4 = wait_record(log, lambda x: x.get("est_answer_chars") == 0
                       and x.get("status") == 200
                       and any("未见 data: [DONE]" in n for n in (x.get("notes") or [])))
    check("C1 断流被明确记录（未见 [DONE] 提示，不谎报成功）", rec4 is not None)

    # ---------------- C3: 单槽串行化与排队时间 ----------------
    Mock.max_inflight = 0
    results = {}

    def worker(k):
        results[k] = post(pport, "immediate")

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    t0 = time.monotonic()
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    elapsed = time.monotonic() - t0
    check("C3 上游同时只被一个请求占用（代理串行化 -np 1 单槽）",
          Mock.max_inflight == 1, Mock.max_inflight)
    check("C3 两个并发请求都被完整转发", all(x["body"].count(b"[DONE]") == 1
                                              for x in results.values()),
          [len(x["body"]) for x in results.values()])
    recs = [x for x in read_records(log) if x.get("status") == 200
            and x.get("queue_ms") is not None]
    check("C3 排队时间可观测（有一个请求 queue_ms>=300）",
          any((x.get("queue_ms") or 0) >= 300 for x in recs),
          [x.get("queue_ms") for x in recs])
    check("C3 串行化确实拉长了总时长（>=1.1s 两个 0.6s 串行）",
          elapsed >= 1.1, "elapsed=%.2fs" % elapsed)

    # ---------------- C2: 客户端取消 + 后端释放验证 ----------------
    conn = http.client.HTTPConnection("127.0.0.1", pport, timeout=30)
    body = json.dumps({"model": "bonsai-2-27b",
                       "messages": [{"role": "user", "content": "hi"}],
                       "stream": True, "mock_behavior": "cancel"}).encode()
    conn.request("POST", "/v1/chat/completions", body=body,
                 headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    resp.read1(4096)
    # 必须显式 resp.close()：响应带 Connection: close 时，getresponse() 已把
    # conn.sock 置空，真正持有 fd 的是 resp.fp；只 conn.close() 不会发 FIN，
    # 那样“客户端”其实一直连着，代理当然判不出取消（夹具缺陷，非代理缺陷）。
    resp.close()
    conn.close()                       # 客户端中途“跑掉”（真断开 TCP）
    rec5 = wait_record(log, lambda x: x.get("client_disconnected") is True, timeout=8)
    check("C2 客户端取消被记录（client_disconnected）", rec5 is not None)
    check("C2 取消后验证后端 /slots 释放（不假设 close 即取消）",
          rec5 is not None and rec5.get("release_verified") is not None,
          None if rec5 is None else rec5.get("release_verified"))

    # ---------------- C4: 字段齐全 ----------------
    need = ["request_id", "start_at", "end_at", "model", "config_hash", "profile",
            "status", "finish_reason", "stop_type", "truncated",
            "input_tokens_total", "prompt_evaluated_tokens", "cache_reused_tokens",
            "reasoning_tokens", "answer_tokens", "tool_argument_tokens",
            "completion_tokens", "queue_ms", "prefill_ms", "first_stream_event_ms",
            "first_reasoning_ms", "first_visible_content_ms", "generation_ms",
            "wall_ms", "decode_tps", "client_disconnected", "timeout_kind",
            "error_type", "cache_reuse"]
    allrec = read_records(log)
    sample = [x for x in allrec if x.get("est_answer_chars") == 4]
    sample = sample[0] if sample else (allrec[-1] if allrec else {})
    missing = [k for k in need if k not in sample]
    check("C4 requests.jsonl 字段齐全（方案 §C4 清单）", not missing, missing)
    check("C4 每请求有独立 request_id", bool(sample.get("request_id")))

    # ---------------- C4: 复用分档取代旧判据 ----------------
    check("C4 reuse_class 无复用", P.reuse_class(100, 0) == "无复用")
    check("C4 reuse_class 部分复用", P.reuse_class(7000, 3000) == "部分复用")
    check("C4 reuse_class 高比例复用", P.reuse_class(6000, 60000) == "高比例复用")
    check("C4 reuse_class 未知（无计数）", P.reuse_class(None, None) == "未知")
    check("C4 reuse_class 全复用（prompt_n=0）", P.reuse_class(0, 500) == "高比例复用")
    txt = P.write_verdict()
    check("C4 verdict.txt 已删除“prompt_n < 1500”绝对判据",
          "prompt_n < 1500" not in txt and "复用" in txt,
          [ln for ln in txt.splitlines() if "1500" in ln])
    check("C4 timings.jsonl 不再写 hit 绝对字段",
          all("hit" not in x for x in read_records(P.timings_path())))

    # ---------------- C2: 三档超时（用更小的超时值触发）----------------
    P.CFG["timeouts"].update({"first_response_s": 0.5, "stream_idle_s": 0.4,
                              "overall_s": 0.5, "client_write_s": 2,
                              "release_wait_s": 1})
    r6 = post(pport, "slow_first")
    check("C2 首字超时 -> 504（timeout_kind=first_response）",
          r6["status"] == 504, r6["status"])
    rec6 = wait_record(log, lambda x: x.get("timeout_kind") == "first_response")
    check("C2 首字超时被记录并带 release 验证结果",
          rec6 is not None and rec6.get("release_verified") is not None,
          None if rec6 is None else rec6.get("release_verified"))

    r7 = post(pport, "stall")
    rec7 = wait_record(log, lambda x: x.get("timeout_kind") == "no_data")
    check("C2 无数据超时 -> no_data 且已转发部分保留",
          rec7 is not None and r7["body"].startswith(EV_ROLE),
          None if rec7 is None else rec7.get("timeout_kind"))

    r8 = post(pport, "dribble")
    rec8 = wait_record(log, lambda x: x.get("timeout_kind") == "overall")
    check("C2 整体超时 -> overall（心跳/小块数据不断时也不能无限拖）",
          rec8 is not None and r8["body"].startswith(EV_ROLE),
          None if rec8 is None else rec8.get("timeout_kind"))

    # ---------------- 收尾 ----------------
    srv.shutdown()
    mock.shutdown()
    print()
    print("== 结果: %d 通过 / %d 失败 ==" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项:")
        for f in FAIL:
            print("  - " + f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())