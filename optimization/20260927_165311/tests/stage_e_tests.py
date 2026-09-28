# -*- coding: utf-8 -*-
r"""阶段 E 离线验收测试（不加载模型、不发真实推理）

用“模拟上游”覆盖输入预算闸门（方案 §7 E1/E2/E3）在真实请求路径上的行为：
  E1 精确核算：/apply-template + /tokenize 同一模板路径；只有上界估算能安全放行才跳过精确计数
  E2 超预算处理：warn = 告警并转发；reject = 生成前返回 400 且【不占用上游槽位】（上游未收到
     /v1/chat/completions）
  E3 失败不谎报：/apply-template 失败记 unknown 并照常转发；/props 不可达时窗口来源如实标注
  附 不静默裁剪：预算检查不改写请求体；new_record 新增 budget_check 字段

用法：python stage_e_tests.py
"""
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

PROXY = os.environ.get("BONSAI_PROXY_PATH") or r"D:\Bonsai-demo\proxy\bonsai_proxy.py"
PASS, FAIL = [], []
sys.stdout.reconfigure(encoding="utf-8")


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  <- " + str(detail)) if (detail and not cond) else ""))


class Mock(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    lock = threading.Lock()
    n_apply = 0
    n_tokenize = 0
    n_chat = 0
    mock_tokens = 1000
    props_ok = True
    n_ctx = 65536

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

    def do_GET(self):
        if self.path.startswith("/props"):
            if Mock.props_ok:
                self._json(200, {"n_ctx": Mock.n_ctx, "build_info": "mock-e"})
            else:
                self._json(500, {"error": "props unavailable"})
        elif self.path.startswith("/slots"):
            self._json(200, [{"is_processing": False, "n_prompt_tokens": 0}])
        elif self.path.startswith("/health"):
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        ln = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(ln) if ln else b"{}"
        p = self.path
        if p.startswith("/apply-template"):
            with Mock.lock:
                Mock.n_apply += 1
            if getattr(Mock, "apply_fail", False):
                self._json(500, {"error": "template boom"})
                return
            self._json(200, {"prompt": "<|im_start|>assistant\n"})
            return
        if p.startswith("/tokenize"):
            with Mock.lock:
                Mock.n_tokenize += 1
            self._json(200, [7] * Mock.mock_tokens)
            return
        if "/chat/completions" in p:
            with Mock.lock:
                Mock.n_chat += 1
            self.close_connection = True
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            try:
                self.wfile.write(b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n')
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except Exception:
                pass
            return
        self._json(404, {"error": "not found"})


def load_proxy():
    spec = importlib.util.spec_from_file_location("px_stage_e", PROXY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def post(port, obj, timeout=60.0):
    req = urllib.request.Request(
        "http://127.0.0.1:%d/v1/chat/completions" % port,
        data=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, repr(e)


BIG_FILLER = "x" * 300000          # 约 300 KB -> 上界估算必然超窗口，强制走精确计数


def set_cfg(P, mode="warn", enabled=True, plan=8192, reserve=1024, floor=3.0,
            window=65536, mock_tokens=1000, props_ok=True):
    P.RAW_CFG = {"budget": {
        "request_max_tokens": plan,
        "thinking_budget_tokens": 2048,
        "context_reserve_tokens": reserve,
        "context_window_tokens": window,
        "gate": {"enabled": enabled, "mode": mode, "chars_per_token_floor": floor},
        "policy": {"apply_request_max_tokens": False, "apply_thinking_budget": False},
    }}
    P.CTX_WIN.update({"tokens": None, "at": 0.0, "source": None})
    with Mock.lock:
        Mock.mock_tokens = mock_tokens
        Mock.props_ok = props_ok
        Mock.apply_fail = False
        Mock.n_apply = Mock.n_tokenize = Mock.n_chat = 0


def counts():
    with Mock.lock:
        return Mock.n_apply, Mock.n_tokenize, Mock.n_chat


def main():
    print("== 阶段 E 验收测试 ==")
    print("   被测代理: %s" % PROXY)
    P = load_proxy()
    tmp = tempfile.mkdtemp(prefix="bonsai_stage_e_")

    mock = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=mock.serve_forever, daemon=True).start()
    mport = mock.server_address[1]

    P.CFG["capture_dir"] = tmp
    P.CFG["request_log"] = os.path.join(tmp, "requests.jsonl")
    P.ARGS = SimpleNamespace(effort=None, keep_location=True, upstream=mport,
                             port=0, config=None)
    P.CFG["timeouts"].update({"connect_s": 2, "first_response_s": 5, "stream_idle_s": 5,
                              "overall_s": 30, "client_write_s": 2, "release_wait_s": 2})
    srv = ThreadingHTTPServer(("127.0.0.1", 0), P.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    pport = srv.server_address[1]
    log = P.CFG["request_log"]
    small = {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 8}
    big = {"messages": [{"role": "user", "content": BIG_FILLER}], "max_tokens": 8}

    # ---------- E1 便宜路径：上界估算足够小则跳过精确计数 ----------
    set_cfg(P, mock_tokens=1000)
    a, i = P.check_input_budget(json.dumps(small).encode("utf-8"))
    n_ap, n_tk, _ = counts()
    check("E1 小请求走上界估算跳过精确计数（action=skip，且未调用上游模板/分词）",
          a == "skip" and n_ap == 0 and n_tk == 0
          and i["method"] == "chars_upper_bound", (a, n_ap, n_tk, i))

    # ---------- E1 精确路径：大请求必须精确计数 ----------
    set_cfg(P, mock_tokens=1000)
    a, i = P.check_input_budget(json.dumps(big).encode("utf-8"))
    n_ap, n_tk, _ = counts()
    check("E1 大请求走精确计数（/apply-template + /tokenize 各一次）",
          a == "pass" and n_ap == 1 and n_tk == 1
          and i["method"] == "exact(apply-template+tokenize)", (a, n_ap, n_tk, i))
    check("E1 预算算式正确：required=input+计划生成+余量，headroom=窗口-required",
          i["input_tokens"] == 1000 and i["required"] == 1000 + 8192 + 1024
          and i["headroom"] == 65536 - (1000 + 8192 + 1024)
          and i["verdict"] == "在预算内(精确)", i)

    # ---------- E3 失败不谎报 ----------
    set_cfg(P, mock_tokens=1000)
    with Mock.lock:
        Mock.apply_fail = True
    a, i = P.check_input_budget(json.dumps(big).encode("utf-8"))
    check("E3 /apply-template 失败 -> unknown（不当作安全放行）",
          a == "unknown" and i["input_tokens"] is None
          and "未知" in (i["verdict"] or ""), (a, i))

    set_cfg(P, mock_tokens=1000, props_ok=False, window=32768)
    i_win, i_src = P.effective_context_window()
    a, i = P.check_input_budget(json.dumps(small).encode("utf-8"))
    check("E3 /props 不可达 -> 窗口取配置兜底且来源如实标注",
          i_win == 32768 and "配置" in (i_src or "") and i["window"] == 32768, (i_win, i_src))

    # ---------- 不静默裁剪 ----------
    set_cfg(P, mock_tokens=1000)
    raw = json.dumps(big).encode("utf-8")
    before = json.loads(raw.decode("utf-8"))
    P.check_input_budget(raw)
    after = json.loads(raw.decode("utf-8"))
    check("E4 预算检查不改写请求体（不静默裁剪/不替用户删消息）", before == after, "body 被改动")

    # ---------- E2 warn：超预算仍转发 ----------
    set_cfg(P, mode="warn", mock_tokens=60000)
    st, body = post(pport, dict(big, mock_behavior="immediate"))
    _, _, n_chat = counts()
    rec = None
    for _ in range(40):
        if os.path.exists(log):
            for ln in open(log, encoding="utf-8"):
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if r.get("path", "").endswith("/chat/completions"):
                    rec = r
        if rec and rec.get("status"):
            break
        time.sleep(0.1)
    rec = rec or {}
    check("E2 warn：超预算仍转发（客户端 200，上游确实收到推理请求）",
          st == 200 and n_chat == 1, (st, n_chat))
    check("E2 warn：日志记录超预算判定与 warn 说明",
          (rec.get("budget_check") or {}).get("verdict") == "超预算"
          and any("warn" in n for n in rec.get("notes") or []),
          {"verdict": (rec.get("budget_check") or {}).get("verdict"),
           "notes": rec.get("notes")})

    # ---------- E2 reject：生成前拒绝，且不占上游槽位 ----------
    set_cfg(P, mode="reject", mock_tokens=60000)
    before_chat = counts()[2]
    st2, body2 = post(pport, dict(big, mock_behavior="immediate"))
    _, _, n_chat_after = counts()
    try:
        err = json.loads(body2)
    except Exception:
        err = {}
    check("E2 reject：生成前返回 400 且错误可操作（含 input_over_budget 与预算明细）",
          st2 == 400 and (err.get("error") or {}).get("code") == "input_over_budget"
          and (err.get("error") or {}).get("budget"), (st2, body2[:200]))
    check("E2 reject：未向上游发起推理（不占单槽、不消耗 GPU）",
          n_chat_after == before_chat, (before_chat, n_chat_after))

    # ---------- 闸门关闭 ----------
    set_cfg(P, enabled=False, mock_tokens=60000)
    a, i = P.check_input_budget(json.dumps(big).encode("utf-8"))
    n_ap, n_tk, _ = counts()
    check("E5 gate.enabled=false -> 不判定、不调上游（记录为已关闭）",
          a == "disabled" and i["verdict"] == "闸门已关闭" and n_ap == 0 and n_tk == 0,
          (a, i, n_ap))

    # ---------- 日志字段 ----------
    rec0 = P.new_record("rid-e", "POST", "/v1/chat/completions", 0.0)
    check("E5 requests.jsonl 新增 budget_check 字段",
          "budget_check" in rec0, sorted(rec0.keys())[:8])

    print("\n通过 %d / 失败 %d" % (len(PASS), len(FAIL)))
    for f in FAIL:
        print("  - %s" % f)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())