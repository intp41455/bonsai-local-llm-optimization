# -*- coding: utf-8 -*-
r"""
bonsai_proxy.py —— 透明反向代理 + 请求抓包 + KV 预热（v2）

WHY（2026-09-27 抓包实证，已推翻两个旧假设）
    实测（用 /apply-template 渲染真实 prompt 后逐字节比对）：
      req_004 56,738 tok  --\  公共前缀 56,738 tok  复用 99.4%   B 段实测 1.5 s
      req_005 57,061 tok  --/  公共前缀 57,061 tok  复用 98.6%   C 段实测 3.0 s
      req_006 57,885 tok
    => WorkBuddy 是【严格追加】：system(35,369 字符) 与 user[1](44,143 字符)
       三轮逐字节不变，新内容只追加在尾巴。前缀稳定问题【不存在】。
    => <current_time> 不在 system 里，而在 <system-reminder data-role="user-context">
       块内、随新 user 消息追加在最后。旧假设"时间戳击穿 tools 前缀"作废。

    实测冷/热对比（_cap_replay.py）：
      A 冷启动 req_004   125.3 s   prompt_n=56,738   454.5 t/s   <-- 只有这一档慢
      B 追加   req_005     1.5 s   prompt_n=327
      C 追加   req_006     3.0 s   prompt_n=828
      D 旁路小请求          1.4 s   prompt_n=80
      E 旁路后再发 req_006  1.0 s   prompt_n=4        <-- 旁路调用【不会】冲掉缓存
    => 慢的唯一来源是【服务刚起来后的第一次请求】；之后全部 1~3 秒。
    => 旧假设"摘要调用冲掉 slot 缓存"也作废（llama-server 会保留多个缓存状态）。

TOOLS（本代理的解法）
    在服务启动后立刻用上一份真实请求体重放一次（max_tokens=1），把 125 秒的
    冷启动代价挪到"没人等"的时候；WorkBuddy 的首条消息落地即成缓存命中（~2 s）。

ARCHITECTURE
    WorkBuddy  -->  :8080 (本代理)  -->  :8081 (llama-server)
    客户端配置不用改。--warm 时开一个后台线程先焐热 KV，再正常服务。

OUTPUT
    capture/req_<n>_<ts>.json    完整请求体
    capture/timings.jsonl        每次请求的 prompt_n / prefill_ms / 是否命中
    capture/verdict.txt          前缀稳定性判定

USAGE
    python bonsai_proxy.py                        # 仅抓包 + 瘦身
    python bonsai_proxy.py --warm                 # 抓包 + 启动时预热（推荐）
    python bonsai_proxy.py --warm-file X.json     # 指定用哪份请求体预热
    python bonsai_proxy.py --effort medium        # 额外注入思考档位（治"雷霆大思考"）
    python bonsai_proxy.py --keep-location        # 关闭请求瘦身（A/B 对照用）
    python bonsai_proxy.py --verdict              # 只看判定

REQUEST SLIMMING（2026-09-27 新增，治"冷启动太慢"）
    实测单条真实 Agent 请求的 prompt 由三块组成（/tokenize 精确计量）：
        tools      32,515 tok  54.3%   <- 最大头
          └ Skill  11,538 tok  35.5% of tools
              └ description 11,181 tok，其中 149 条 (location: 绝对路径) = 5,050 tok
          └ ToolSearch 3,034 tok，其中 deferred 清单 = 2,502 tok
          └ Agent      2,041 tok，其中子代理清单 = ~1,200 tok
        system     14,464 tok  24.2%
        messages   12,860 tok  21.5%
    三类都是【清单/路径】，模型按名调用工具/技能，不读这些 -> 纯噪音。
    本代理默认在转发前剥掉，每次省约 8,626 tok（14.8%），冷启动 prefill 相应缩短约 19 秒。
    替换是确定性的 -> 前缀稳定 -> 与预热天然对齐。

REASONING_EFFORT（治过度思考，见 _effort_test.py 实测）
    模型内置模板原生支持三档，【默认 xhigh】——即下载即用等于全程顶配思考。
    本代理可代客户端注入，这样 Agent 场景不必改 WorkBuddy 任何配置：
        --effort off     关闭思考（最快，但实测会把"绕圈"搬到可见答案里，最不推荐）
        --effort low     要求简短、直接给结论
        --effort medium  不注入任何思考指令 = 模型自然行为（实测性价比最高）
        --effort xhigh   默认档，最啰嗦
"""
import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CAP = r"D:\Bonsai-demo\capture"
os.makedirs(CAP, exist_ok=True)

ARGS = None
STATE = {"n": 0, "last": None, "lock": threading.Lock()}

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

HOP = {"host", "connection", "keep-alive", "proxy-authenticate",
       "proxy-authorization", "te", "trailers", "transfer-encoding",
       "upgrade", "content-length", "accept-encoding"}

TIMINGS = os.path.join(CAP, "timings.jsonl")
EFFORT_FILE = os.path.join(CAP, "effort.txt")


def common_prefix_len(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


# ---------------------------------------------------------------- 请求瘦身
LOC_RE = re.compile(r"\s*\(location: [^)]*\)")
DEFERRED_RE = re.compile(
    r"<available_deferred_tools>.*?</available_deferred_tools>", re.S)
SUBAGENT_RE = re.compile(
    r"<avaliable_subagents>.*?</avaliable_subagents>", re.S)


def strip_locations(raw):
    """剥掉 tools 描述里的三类纯噪音块（均为【清单/路径】，模型按名调用，不读这些）。

    实测（2026-09-27 12:21 真实请求，用上游 /tokenize 精确计量）：

    ┌─────────────────────────────────────┬────────┬──────┬────────┐
    │ 优化项                               │ 净省tok│ 占比 │ 代价    │
    ├─────────────────────────────────────┼────────┼──────┼────────┤
    │ ① 剥 (location: C:/.../SKILL.md)    │  4,931 │ 8.4% │ 零      │
    │ ② 剋 ToolSearch deferred 工具清单    │  2,512 │ 4.3% │ 多一跳  │
    │ ③ 剋 Agent 子代理类型清单            │ ~1,200 │ 2.1% │ 不用=无害│
    ├─────────────────────────────────────┼────────┼──────┼────────┤
    │ 合计                                  │  8,626 │14.8% │         │
    └─────────────────────────────────────┴────────┴──────┴────────┘

    三项都是【确定性正则替换】 -> 同一请求每次得到逐字节相同结果 ->
    前缀稳定 -> 不破坏 KV 复用。预热与实际请求走同一管线，前缀天然对齐。

    用 --keep-location 可关闭全部瘦身（用于 A/B 对照）。
    """
    try:
        d = json.loads(raw.decode("utf-8", "ignore"))
    except Exception:
        return raw, 0
    if not isinstance(d, dict):
        return raw, 0
    saved = 0
    for t in d.get("tools") or []:
        fn = t.get("function") if isinstance(t, dict) else None
        if not isinstance(fn, dict):
            continue
        desc = fn.get("description")
        if not isinstance(desc, str):
            continue
        orig = desc
        # ① 剥磁盘路径
        if "(location:" in desc:
            desc = LOC_RE.sub("", desc)
        # ② 压缩 ToolSearch 的 deferred 工具清单（129 条，2502 tok）
        if "<available_deferred_tools>" in desc:
            desc = DEFERRED_RE.sub(
                "<available_deferred_tools>(names omitted; "
                "call ToolSearch to discover)</available_deferred_tools>", desc)
        # ③ 压缩 Agent 的子代理类型清单（9 条，约 1200 tok）
        if "<avaliable_subagents>" in desc:
            desc = SUBAGENT_RE.sub(
                "<avaliable_subagents>(types omitted; "
                "specify subagent_type when needed)</avaliable_subagents>", desc)
        if desc != orig:
            saved += len(orig) - len(desc)
            fn["description"] = desc
    if not saved:
        return raw, 0
    return json.dumps(d, ensure_ascii=False).encode("utf-8"), saved


# ---------------------------------------------------------------- 预热
def pick_newest_capture(min_chars=20000):
    """挑一份"像 Agent 请求"的抓包来预热。

    两条都要满足：
      1) 体积够大（真实 Agent 请求约 22 万字符）——否则会挑到自己发的小测试请求
         （一两百字节），预热等于空转；
      2) 时间最新——WorkBuddy 的 system prompt 会随版本 / 界面语言 / 技能集
         变化而改变（实测 05:31 的 system 35,369 字符 vs 12:21 的 52,514 字符，
         公共前缀只剩 1,382 字符，拿旧版预热 = 完全没热）。所以必须用【当前
         版本产生的最后一份】大请求来预热。
    """
    cands = []
    for f in os.listdir(CAP):
        if f.startswith("req_") and f.endswith(".json"):
            p = os.path.join(CAP, f)
            try:
                cands.append((os.path.getsize(p), os.path.getmtime(p), p))
            except OSError:
                pass
    if not cands:
        return None
    big = [c for c in cands if c[0] >= min_chars]
    pool = big or cands
    pool.sort(key=lambda c: c[1])          # 取 mtime 最新
    return pool[-1][2]


def apply_effort(body_bytes):
    """按 --effort 给对话请求注入思考档位（模型模板原生支持 reasoning_effort）。

    模型内置模板实测（/props 的 chat_template）：
        reasoning_effort 默认 'xhigh'，可选 xhigh / medium / low
        xhigh  -> 注入"请仔细思考、验证假设、考虑替代方案"
        medium -> 【不注入任何指令】（即模型自然行为）
        low    -> 注入"保持简短、直接给结论"
        enable_thinking=false -> 完全不思考
    客户端未显式指定时才注入，避免覆盖调用方意图。
    """
    if not ARGS or not getattr(ARGS, "effort", None):
        return body_bytes, None
    try:
        d = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        return body_bytes, None
    if not isinstance(d, dict) or "messages" not in d:
        return body_bytes, None
    ck = d.get("chat_template_kwargs")
    if not isinstance(ck, dict):
        ck = {}
    if ARGS.effort == "off":
        if "enable_thinking" in ck or "reasoning_effort" in ck:
            return body_bytes, "客户端已自行指定，跳过"
        ck["enable_thinking"] = False
    else:
        if "reasoning_effort" in ck:
            return body_bytes, "客户端已自行指定，跳过"
        ck["reasoning_effort"] = ARGS.effort
    d["chat_template_kwargs"] = ck
    return json.dumps(d, ensure_ascii=False).encode("utf-8"), ARGS.effort


def prewarm(path=None, upstream=8081, tag="预热"):
    """重放一份真实请求体（max_tokens=1），把 KV 缓存焐热。"""
    path = path or pick_newest_capture()
    if not path or not os.path.exists(path):
        print("[%s] 没有可用请求体（capture/req_*.json 为空），跳过" % tag, flush=True)
        return None
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print("[%s] 读取失败 %r" % (tag, e), flush=True)
        return None
    body = dict(d)
    body["stream"] = False
    body.pop("stream_options", None)
    body["max_tokens"] = 1
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if not getattr(ARGS, "keep_location", False):
        raw, sl = strip_locations(raw)
        if sl:
            print("[%s] 瘦身：剥离 (location: ...) %d 字符（与真实请求走同一管线）"
                  % (tag, sl), flush=True)
    data, note = apply_effort(raw)
    if note:
        print("[%s] 按 --effort=%s 构造（与实际请求前缀保持一致，否则预热白做）"
              % (tag, note), flush=True)
    req = urllib.request.Request("http://127.0.0.1:%d/v1/chat/completions" % upstream,
                                 data=data, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with _opener.open(req, timeout=3600) as r:
            out = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print("[%s] 失败 %r（上游还没起来？）" % (tag, e), flush=True)
        return None
    dt = time.time() - t0
    tm = out.get("timings") or {}
    pn = tm.get("prompt_n")
    print("[%s] 用 %s" % (tag, os.path.basename(path)), flush=True)
    print("       prompt_n=%s   prefill=%.1f s   wall=%.1f s" % (
        pn, (tm.get("prompt_ms") or 0) / 1000.0, dt), flush=True)
    if pn and pn > 1000:
        print("       >> 原来还没热，全量 prefill %.1f 秒。现在已焐热，"
              "WorkBuddy 首条消息将直接命中。" % (dt), flush=True)
    else:
        print("       >> 缓存已是热的（prompt_n=%s），无需重算。" % pn, flush=True)
    try:
        with open(TIMINGS, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "kind": tag, "src": os.path.basename(path),
                                "prompt_n": pn,
                                "prefill_s": round((tm.get("prompt_ms") or 0) / 1000.0, 2),
                                "hit": bool(pn and pn < 1500),
                                "wall_s": round(dt, 2)},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass
    return pn


def log_timings(tag, tail_bytes):
    """从流式响应的尾部把 timings 抠出来存档，用于持续监控缓存命中率。"""
    try:
        t = tail_bytes.decode("utf-8", "ignore")
    except Exception:
        return
    m = re.search(r'"prompt_n"\s*:\s*(\d+)', t)
    if not m:
        return
    pn = int(m.group(1))
    pm = re.search(r'"prompt_ms"\s*:\s*([\d.]+)', t)
    cn = re.search(r'"cache_n"\s*:\s*(\d+)', t)
    ps = re.search(r'"predicted_per_second"\s*:\s*([\d.]+)', t)
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "kind": tag,
           "prompt_n": pn,
           "prefill_s": round(float(pm.group(1)) / 1000.0, 2) if pm else None,
           "cache_n": int(cn.group(1)) if cn else None,
           "decode_tps": round(float(ps.group(1)), 2) if ps else None}
    hit = (pn < 1500)
    rec["hit"] = hit
    try:
        with open(TIMINGS, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    print("     >> %s  prompt_n=%d  prefill=%ss  decode=%s t/s" % (
        "缓存命中 1~3 秒级" if hit else "冷启动（全量重算）",
        pn, rec["prefill_s"], rec["decode_tps"]), flush=True)


# ---------------------------------------------------------------- 分析
def analyze(body_bytes, n):
    try:
        d = json.loads(body_bytes.decode("utf-8", "ignore"))
    except Exception:
        return None

    msgs = d.get("messages") or []
    tools = d.get("tools") or []
    sys_txt = ""
    for m in msgs:
        if m.get("role") == "system":
            c = m.get("content")
            sys_txt = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False)
            break
    tool_txt = json.dumps(tools, ensure_ascii=False, sort_keys=True)
    body_txt = body_bytes.decode("utf-8", "ignore")

    rec = {
        "n": n,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "body_chars": len(body_txt),
        "n_messages": len(msgs),
        "n_tools": len(tools),
        "system_chars": len(sys_txt),
        "tools_chars": len(tool_txt),
        "system_head": sys_txt[:180],
        "system_tail": sys_txt[-180:],
    }

    # Agent 级请求（体积大）才叫 req_*，自己的小测试单独放，免得被当成预热素材
    prefix = "req" if len(body_txt) >= 20000 else "small"
    with open(os.path.join(CAP, "%s_%03d_%s.json" % (prefix, n, time.strftime("%H%M%S"))),
              "w", encoding="utf-8") as f:
        f.write(body_txt)

    prev = STATE.get("last")
    if prev:
        r = {
            "d_full": common_prefix_len(body_txt, prev["body_txt"]),
            "d_sys": common_prefix_len(sys_txt, prev["sys_txt"]),
        }
        r["pct_full"] = r["d_full"] / max(1, len(body_txt))
        r["pct_sys"] = r["d_sys"] / max(1, len(sys_txt))
        rec["diff"] = r

    STATE["last"] = {"body_txt": body_txt, "sys_txt": sys_txt}
    return rec


def write_verdict():
    """判定：靠真实响应里的 prompt_n 认，不靠字符串比长度猜。"""
    lines = ["Bonsai 前缀稳定性 & 缓存命中判定", "=" * 62, ""]
    recs = []
    if os.path.exists(TIMINGS):
        for ln in open(TIMINGS, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    recs.append(json.loads(ln))
                except Exception:
                    pass
    if not recs:
        lines.append("还没有 timings 记录。让 WorkBuddy 发一条消息再看。")
    else:
        lines.append("%-20s %-7s %9s %10s %8s %s" %
                     ("时间", "类型", "prompt_n", "prefill_s", "命中", "decode_t/s"))
        lines.append("-" * 62)
        for r in recs[-25:]:
            pn = r.get("prompt_n")
            hit = r.get("hit")
            if hit is None and isinstance(pn, int):
                hit = pn < 1500
            lines.append("%-20s %-7s %9s %10s %8s %s" % (
                r.get("ts", ""), r.get("kind", ""), pn,
                r.get("prefill_s", ""), "是" if hit else "否",
                r.get("decode_tps", "")))
        hits = [r for r in recs if r.get("kind") not in ("预热", "启动预热", "体检")]
        if hits:
            nh = sum(1 for r in hits
                     if (r.get("hit") if r.get("hit") is not None
                         else (r.get("prompt_n") or 0) < 1500))
            lines += ["", "对话请求命中率: %d/%d" % (nh, len(hits))]
    lines += ["", "判据：prompt_n < 1500  -> 缓存命中，1~3 秒出首字；",
              "      prompt_n = 全量  -> 冷启动，约 125 秒（此后再快）。",]
    txt = "\n".join(lines)
    with open(os.path.join(CAP, "verdict.txt"), "w", encoding="utf-8") as f:
        f.write(txt)
    return txt


# ---------------------------------------------------------------- 代理
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "bonsai-proxy/2.0"

    def log_message(self, fmt, *a):
        pass

    def _forward(self, method):
        ln = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(ln) if ln else None

        if body and "/chat/completions" in self.path:
            with STATE["lock"]:
                STATE["n"] += 1
                n = STATE["n"]
            rec = analyze(body, n)
            if rec:
                d = rec.get("diff")
                print("\n[#%d] system=%d tools=%d msgs=%d" % (
                    rec["n"], rec["system_chars"], rec["tools_chars"],
                    rec["n_messages"]), flush=True)
                if d:
                    print("     与上一请求公共前缀 %.1f%%" % (d["pct_full"] * 100),
                          flush=True)

        if body and "/chat/completions" in self.path:
            if not getattr(ARGS, "keep_location", False):
                body, saved = strip_locations(body)
                if saved:
                    print("     [瘦身] 剥离 (location: ...) %d 字符" % saved, flush=True)
            body, note = apply_effort(body)
            if note:
                print("     [effort] 注入 reasoning_effort = %s" % note, flush=True)

        url = "http://127.0.0.1:%d%s" % (ARGS.upstream, self.path)
        hdrs = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            resp = _opener.open(req, timeout=3600)
        except urllib.error.HTTPError as e:
            resp = e
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            msg = json.dumps({"error": {"message": "proxy upstream error: %r" % e}}).encode()
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            return

        status = getattr(resp, "status", 200) or 200
        self.send_response(status)
        for k, v in resp.headers.items():
            if k.lower() in ("transfer-encoding", "connection", "content-length"):
                continue
            self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()

        tail = bytearray()
        try:
            while True:
                chunk = resp.read(2048)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                tail.extend(chunk)
                if len(tail) > 16384:
                    del tail[:len(tail) - 16384]
        except Exception:
            pass
        try:
            resp.close()
        except Exception:
            pass

        if body and "/chat/completions" in self.path and tail:
            threading.Thread(target=log_timings, args=("对话", bytes(tail)),
                             daemon=True).start()

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def do_PUT(self):
        self._forward("PUT")

    def do_DELETE(self):
        self._forward("DELETE")

    def do_OPTIONS(self):
        self._forward("OPTIONS")


def serve():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--upstream", type=int, default=8081)
    ap.add_argument("--warm", action="store_true", help="启动时用最近的请求体预热 KV")
    ap.add_argument("--warm-file", default=None)
    ap.add_argument("--effort", default=None,
                    choices=["off", "low", "medium", "xhigh"],
                    help="给对话请求注入思考档位，不改客户端。off=关闭思考；"
                         "medium=不注入任何思考指令（模型自然行为，推荐 Agent 场景）")
    ap.add_argument("--keep-location", action="store_true",
                    help="不剥离 (location: ...)（关闭瘦身，用于 A/B 对照）")
    ARGS = ap.parse_args()

    # 把生效的思考档位落盘，供 warm_kv.py 对齐预热（档位是 system 前缀的一部分，
    # 预热用错档位 = 前缀不匹配 = 等于没预热）。
    eff = ARGS.effort or "xhigh"   # 不注入 == 模型默认档 xhigh，两者注入的指令逐字节相同
    try:
        with open(EFFORT_FILE, "w", encoding="utf-8") as f:
            f.write(eff)
    except Exception:
        pass

    print("=" * 66)
    print(" Bonsai 抓包代理 v2   :%d  -->  llama-server :%d" % (ARGS.port, ARGS.upstream))
    print("   抓包目录: %s" % CAP)
    if ARGS.effort:
        print("   思考档位: 注入 reasoning_effort=%s（客户端配置不用改）" % ARGS.effort)
    print("   请求瘦身: %s" % ("关闭（--keep-location）" if ARGS.keep_location
                              else "开（① 剥 location ② 压 deferred ③ 压 subagent，省约 8,626 tok/次）"))
    print("=" * 66, flush=True)

    if ARGS.warm or ARGS.warm_file:
        threading.Thread(target=prewarm,
                         args=(ARGS.warm_file, ARGS.upstream, "启动预热"),
                         daemon=True).start()

    srv = ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print(write_verdict())


if __name__ == "__main__":
    if "--verdict" in sys.argv:
        print(write_verdict())
    else:
        serve()
