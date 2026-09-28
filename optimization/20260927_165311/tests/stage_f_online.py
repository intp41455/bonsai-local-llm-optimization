# -*- coding: utf-8 -*-
r"""阶段 F 在线验证（只重启代理；后端 llama-server pid 全程不动）

步骤：
  1) 只读核对：launcher status（在线参数 vs 配置，零差异）
  2) 按【身份】停掉 8080 上的 bonsai_proxy.py（核对 CommandLine），再 launcher up --no-prewarm
  3) 经代理发一个【构造的小请求】：带 tools（含 show_widget 工具体、描述里含 location 路径、
     历史含 2 次 identical 工具失败），max_tokens=1
  4) 读 logs\requests.jsonl 最后一条，核对阶段 F 新字段（slim / tools_hardened / tool_policy /
     tool_arg_audit）确实由【在线运行的代理】写出
  5) 再发一个不带 tools 的请求，确认普通请求不受影响（200）

用法：python stage_f_online.py
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

DEMO = r"D:\Bonsai-demo"
OPT = os.path.join(DEMO, "optimization", "20260927_165311")
REQLOG = os.path.join(DEMO, "logs", "requests.jsonl")
PROXY_URL = "http://127.0.0.1:8080/v1/chat/completions"
LAUNCHER = os.path.join(DEMO, "launcher", "bonsai_launcher.py")
PY = sys.executable
OUT = []
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def say(s=""):
    print(s, flush=True)
    OUT.append(s)


def run(cmd, timeout=120):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="ignore", timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def procs():
    txt = run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
               "$OutputEncoding=[Console]::OutputEncoding=[Text.UTF8Encoding]::new();"
               "Get-CimInstance Win32_Process | Where-Object {$_.Name -match "
               "'llama-server.exe|python.exe'} | "
               "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"])
    try:
        d = json.loads(txt.strip() or "[]")
    except Exception:
        d = []
    if isinstance(d, dict):
        d = [d]
    return d


def proxy_pid():
    for p in procs():
        cl = (p.get("CommandLine") or "")
        if "bonsai_proxy.py" in cl and "--port 8080" in cl:
            return p["ProcessId"], cl
    return None, None


def backend_pid():
    for p in procs():
        if (p.get("Name") or "").lower() == "llama-server.exe":
            return p["ProcessId"]
    return None


def post(body, timeout=600):
    req = urllib.request.Request(PROXY_URL, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.monotonic()
    try:
        with op.open(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "ignore")
        return r.status, raw, round(time.monotonic() - t0, 2)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore"), round(time.monotonic() - t0, 2)
    except Exception as e:
        return None, repr(e), round(time.monotonic() - t0, 2)


def tail_records(n=6):
    if not os.path.exists(REQLOG):
        return []
    lines = [l for l in open(REQLOG, encoding="utf-8", errors="ignore").read().splitlines() if l.strip()]
    out = []
    for l in lines[-n:]:
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- 1) 只读核对
RESTART = "--restart" in sys.argv
say("=" * 74)
say("阶段 F 在线验证%s" % ("" if RESTART else "（复跑：不重启代理）"))
say("=" * 74)
bp0 = backend_pid()
pp0, cl0 = proxy_pid()
if not RESTART:
    say("\n[1-2] 跳过重启：当前代理 pid=%s；后端 llama-server pid=%s" % (pp0, bp0))
    st = run([PY, LAUNCHER, "status"], timeout=180)
    say("\n      launcher status（只读，抽查关键行）:")
    for ln in st.splitlines():
        if any(k in ln for k in ("已并", "代理", "瘦身", "工具体", "在线", "pid=")):
            say("      " + ln.strip())
else:
    say("\n[0] 只读快照：后端 llama-server pid=%s ；代理 bonsai_proxy pid=%s" % (bp0, pp0))
    say("    代理命令行: %s" % cl0)
    st = run([PY, LAUNCHER, "status"], timeout=180)
    say("\n[1] launcher status（只读）:")
    for ln in st.splitlines():
        if ln.strip():
            say("    " + ln)

    # ---------------------------------------------------------------- 2) 只重启代理
    say("\n[2] 按身份停掉代理（只杀 CommandLine 含 bonsai_proxy.py 的 %s）" % pp0)
    if pp0:
        say("    taskkill pid=%s -> %s" % (pp0, run(["taskkill", "/PID", str(pp0), "/F"]).strip()[:120]))
    time.sleep(1.0)
    say("    " + run([PY, LAUNCHER, "up", "--no-prewarm"], timeout=300).strip().replace("\n", "\n    "))
    time.sleep(1.5)
    pp1, cl1 = proxy_pid()
    bp1 = backend_pid()
    say("\n    代理 pid %s -> %s ；后端 pid %s -> %s（后端必须不变）" % (pp0, pp1, bp0, bp1))
    say("    新代理命令行: %s" % cl1)
    say("\n[2b] 新代理启动横幅（logs\\proxy.log 末尾）:")
    plog = os.path.join(DEMO, "logs", "proxy.log")
    if os.path.exists(plog):
        with open(plog, "rb") as f:
            f.seek(max(0, os.path.getsize(plog) - 4000))
            tail = f.read().decode("utf-8", "ignore")
        for ln in tail.splitlines()[-22:]:
            if ln.strip():
                say("    " + ln)
    say("\n    后端保持不变 = %s" % ("是" if bp0 == bp1 and bp1 else "否 ！！"))

# ---------------------------------------------------------------- 3) 构造请求
TOOLS = [{
    "type": "function",
    "function": {
        "name": "show_widget",
        "description": "Show visual content inline. (location: D:/Bonsai-demo/skills/"
                       "dynamic-ui/SKILL.md) Call widget_guidelines first.",
        "parameters": {"type": "object", "required": ["title", "widget_code", "loading_messages"],
                       "properties": {
                           "title": {"type": "string", "description": "Short identifier."},
                           "widget_code": {"type": "string", "description": "SVG or HTML code."},
                           "loading_messages": {
                               "type": "string",
                               "description": "A JSON-encoded string array of 1-4 loading "
                                              "messages. Example: '[\"Preparing chart data\"]'"},
                       }},
    }}, {
    "type": "function",
    "function": {
        "name": "ToolSearch",
        "description": "Discover tools.\n<available_deferred_tools>\n- alpha\n- beta\n"
                       "</available_deferred_tools> (location: D:/Bonsai-demo/x.md)",
        "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
    }}, {
    "type": "function",
    "function": {
        "name": "Agent",
        "description": "Spawn a subagent.\n<avaliable_subagents>\n- Explore\n- Plan\n"
                       "</avaliable_subagents>",
        "parameters": {"type": "object", "properties": {"t": {"type": "string"}}},
    }}]

FAIL = '{"success":false,"loading_messages":[],"message":"loading_messages must contain at least one message."}'
BODY = {
    "model": "bonsai-2-27b",
    "messages": [
        {"role": "system", "content": "SYS-ONLINE-PROBE"},
        {"role": "user", "content": "给一句话。"},
        {"role": "assistant", "tool_calls": [{"id": "c1", "type": "function", "function": {
            "name": "show_widget", "arguments": "{\"title\":\"t\",\"widget_code\":\"<svg/>\"}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": FAIL},
        {"role": "assistant", "tool_calls": [{"id": "c2", "type": "function", "function": {
            "name": "show_widget", "arguments": "{\"title\":\"t\",\"widget_code\":\"<svg></svg>\"}"}}]},
        {"role": "tool", "tool_call_id": "c2", "content": FAIL},
    ],
    "tools": TOOLS,
    "max_tokens": 1,
    "stream": False,
}
n0 = len(tail_records(200))
say("\n[3] 经代理发构造请求（带 tools + 2 次 identical 工具失败，max_tokens=1）")
code, raw, dt = post(BODY)
say("    HTTP %s  %.2fs  响应前 200 字符: %s" % (code, dt, raw[:200].replace("\n", " ")))

# ---------------------------------------------------------------- 4) 核对日志字段
say("\n[4] requests.jsonl 新记录（阶段 F 字段）")
recs = tail_records(200)
last = recs[-1] if recs else {}
say("    记录数 %d -> %d" % (n0, len(recs)))
say("    verdict=%s status=%s wall_ms=%s" % (last.get("verdict"), last.get("status"),
                                             last.get("wall_ms")))
say("    slim         = %s" % json.dumps(last.get("slim"), ensure_ascii=False))
say("    tools_hardened = %s" % json.dumps(last.get("tools_hardened"), ensure_ascii=False))
say("    tool_policy  = %s" % json.dumps(last.get("tool_policy"), ensure_ascii=False))
say("    tool_arg_audit = %s" % json.dumps(last.get("tool_arg_audit"), ensure_ascii=False))
sl = last.get("slim") or {}
fl = sl.get("flags") or {}
sc = sl.get("saved_chars") or {}
aud = last.get("tool_arg_audit") or {}
ok_slim = fl.get("locations") is True and fl.get("deferred_tools") is False \
    and fl.get("subagents") is False and sc.get("locations", 0) > 0 \
    and sc.get("deferred_tools", 0) == 0 and sc.get("subagents", 0) == 0
ok_hard = "show_widget.loading_messages" in (last.get("tools_hardened") or [])
ok_pol = bool(last.get("tool_policy"))
ok_aud = aud.get("tool_failures") == 2 and bool(aud.get("repeated_identical_error")) \
    and aud.get("invalid") == 2
say("    判定: 逐项瘦身=%s / 契约加固=%s / 策略块=%s / 审计(失败2+重复1)=%s"
    % (ok_slim, ok_hard, ok_pol, ok_aud))

# ---------------------------------------------------------------- 5) 普通请求不受影响
say("\n[5] 不带 tools 的请求（回归：普通请求仍 200）")
code2, raw2, dt2 = post({"model": "bonsai-2-27b",
                         "messages": [{"role": "user", "content": "只回一个词：好"}],
                         "max_tokens": 1, "stream": False})
say("    HTTP %s  %.2fs  %s" % (code2, dt2, raw2[:160].replace("\n", " ")))
rec2 = tail_records(200)[-1]
say("    记录 slim=%s tools_hardened=%s tool_policy=%s tool_arg_audit=%s"
    % (rec2.get("slim") is not None, rec2.get("tools_hardened"),
       rec2.get("tool_policy"), rec2.get("tool_arg_audit")))
say("    普通请求 tools_hardened/tool_policy 均为空 = %s"
    % ("是" if not rec2.get("tools_hardened") and not rec2.get("tool_policy") else "否 ！！"))

say("\n[6] 收尾：代理 pid=%s 后端 pid=%s（后端应与开始时一致）" % (proxy_pid()[0], backend_pid()))
say("=" * 74)
open(os.path.join(OPT, "results", "stage_f_online.txt"),
     "a" if not RESTART else "w", encoding="utf-8").write("\n".join(OUT) + "\n")
print("\n结果已写入 results\\stage_f_online.txt")