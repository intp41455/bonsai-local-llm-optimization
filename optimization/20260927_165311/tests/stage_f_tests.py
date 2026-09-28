# -*- coding: utf-8 -*-
r"""阶段 F 离线验收测试（不加载模型、不发真实推理）

方案 §8 阶段 F 的三件事，全部用纯函数 + 真实抓包夹具覆盖：
  F1 工具体契约加固（P05）：show_widget.loading_messages 的描述被替换为精确契约
     （JSON 编码字符串 -> 数组，1–4 个非空字符串 + 最小正确示例 + 失败原文 + 自纠指令）；
     另附 semantic validator（可解析为数组 / 长度 1–4 / 元素字符串）与历史审计观测量。
  F2 瘦身逐项开关（P09）：config.slimming 三项各自独立；deferred 工具清单与子代理
     类型清单在默认配置下【保留】（不再压缩，避免损伤工具发现能力）。
  F4 工具错误恢复策略块：带 tools 的请求在首条 system 文本尾部并入常驻策略；
     不带 tools / 关闭开关 / 重复调用时都不改写。

夹具：D:\Bonsai-demo\capture\req_012_135949.json（真实 Agent 请求，含 show_widget 工具体、
      历史里 2 次 loading_messages 失败原文）

用法：python stage_f_tests.py
"""
import importlib.util
import json
import os
import sys
from types import SimpleNamespace

PROXY = os.environ.get("BONSAI_PROXY_PATH") or r"D:\Bonsai-demo\proxy\bonsai_proxy.py"
CAPTURE = os.environ.get("BONSAI_CAPTURE") or r"D:\Bonsai-demo\capture\req_012_135949.json"
CONFIG = os.environ.get("BONSAI_CONFIG") or r"D:\Bonsai-demo\config\bonsai-agent.json"
LAUNCHER = os.environ.get("BONSAI_LAUNCHER") or r"D:\Bonsai-demo\launcher\bonsai_launcher.py"
PASS, FAIL = [], []
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  <- " + str(detail)) if (detail and not cond) else ""))


def load_proxy():
    spec = importlib.util.spec_from_file_location("bonsai_proxy_f", PROXY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.ARGS = SimpleNamespace(effort=None, keep_location=False, upstream=8081)
    return m


P = load_proxy()
RAW = json.load(open(CAPTURE, encoding="utf-8"))
TOOLS_BODY = json.dumps({"model": "m", "messages": [{"role": "system", "content": "SYS"}],
                         "tools": RAW["tools"]}, ensure_ascii=False).encode("utf-8")
SMALL_BODY = json.dumps({"model": "m", "messages": [{"role": "system", "content": "SYS"},
                                                    {"role": "user", "content": "hi"}]},
                        ensure_ascii=False).encode("utf-8")


def with_flags(**kw):
    P.CFG["slimming"] = {"locations": kw.get("locations", True),
                         "deferred_tools": kw.get("deferred_tools", False),
                         "subagents": kw.get("subagents", False)}


print("=" * 70)
print("阶段 F 离线验收测试   代理=%s" % PROXY)
print("夹具抓包=%s" % CAPTURE)
print("=" * 70)

# ---------------------------------------------------------------- F2 瘦身逐项
print("\nF2 瘦身逐项开关（config.slimming 三项各自独立）")
out_l, s_l, d_l = P.slim_tools(TOOLS_BODY, {"locations": True, "deferred_tools": False,
                                            "subagents": False})
out_d, s_d, d_d = P.slim_tools(TOOLS_BODY, {"locations": False, "deferred_tools": True,
                                            "subagents": False})
out_a, s_a, d_a = P.slim_tools(TOOLS_BODY, {"locations": False, "deferred_tools": False,
                                            "subagents": True})
out_n, s_n, d_n = P.slim_tools(TOOLS_BODY, {"locations": False, "deferred_tools": False,
                                            "subagents": False})
out_all, s_all, d_all = P.slim_tools(TOOLS_BODY, {"locations": True, "deferred_tools": True,
                                                  "subagents": True})

check("locations-only 确实剥掉 (location: ...) 且省字符 > 0",
      s_l > 0 and out_l.count(b"(location:") < TOOLS_BODY.count(b"(location:"), s_l)
check("locations-only 不改动 deferred 名册",
      out_l.count(b"<available_deferred_tools>") == TOOLS_BODY.count(b"<available_deferred_tools>")
      and b"names omitted" not in out_l)
check("locations-only 不改动 subagent 名册",
      out_l.count(b"<avaliable_subagents>") == TOOLS_BODY.count(b"<avaliable_subagents>")
      and b"types omitted" not in out_l)
check("deferred-only：只有 deferred 被压（省字符>0、location 未被剥）",
      s_d > 0 and b"names omitted" in out_d
      and out_d.count(b"(location:") == TOOLS_BODY.count(b"(location:"), s_d)
check("subagent-only：只有 subagent 被压",
      s_a > 0 and b"types omitted" in out_a
      and b"names omitted" not in out_a
      and out_a.count(b"(location:") == TOOLS_BODY.count(b"(location:"), s_a)
check("三项全 false：字节原样、saved=0、明细记 total=0",
      out_n == TOOLS_BODY and s_n == 0 and d_n["total"] == 0)
check("逐项省字符可加和：all == locations + deferred + subagent",
      d_all["saved_chars"]["locations"] > 0
      and d_all["saved_chars"]["deferred_tools"] > 0
      and d_all["saved_chars"]["subagents"] > 0
      and s_all == sum(d_all["saved_chars"][k]
                       for k in ("locations", "deferred_tools", "subagents")))
check("默认配置（locations 开 / 另两项关）时瘦身总收益 < 三项全开（P09 代价已量化）",
      s_l < s_all, (s_l, s_all))
check("确定性：同一输入两次调用逐字节相同（前缀稳定、KV 可复用）",
      P.slim_tools(TOOLS_BODY, d_l["flags"])[0] == out_l
      and P.slim_tools(TOOLS_BODY, d_all["flags"])[0] == out_all)
check("非 JSON / 非 dict 输入：原样返回、saved=0、不抛异常",
      P.slim_tools(b"not-json", {"locations": True})[0] == b"not-json"
      and P.slim_tools(b"[]", {"locations": True})[1] == 0)

with_flags(locations=True)
P.ARGS.keep_location = True
check("ARGS.keep_location=True 时 keep_location() 为真（A/B 对照开关仍有效）",
      P.keep_location() is True)
P.ARGS.keep_location = False
check("默认配置下 keep_location() 为假（locations 开 -> 仍然瘦身）", P.keep_location() is False)
with_flags(locations=False)
check("三项全 false 时 keep_location() 为真（等价于整体关闭）", P.keep_location() is True)
with_flags(locations=True)

# ---------------------------------------------------------------- F1 契约加固
print("\nF1 工具体契约加固（show_widget.loading_messages）")
h_raw, h_detail = P.harden_tool_schemas(TOOLS_BODY)
hb = json.loads(h_raw.decode("utf-8"))
sw = [t for t in hb["tools"] if t.get("function", {}).get("name") == "show_widget"]
check("show_widget 工具体在夹具中存在（P05 的对象确实来自客户端 schema）", len(sw) == 1)
lm = sw[0]["function"]["parameters"]["properties"]["loading_messages"]
desc = lm.get("description", "")
check("重写记录：rewritten 含 show_widget.loading_messages、chars_delta>0",
      "show_widget.loading_messages" in h_detail["rewritten"] and h_detail["chars_delta"] > 0)
check('字段名精确出现（field name exactly "loading_messages"）',
      'field name exactly "loading_messages"' in desc)
check("类型语义写明 JSON-ENCODED STRING + 数组 + 1 to 4 个非空字符串",
      "JSON-ENCODED STRING" in desc and "a JSON array of 1 to 4 non-empty short strings" in desc)
check("最小正确示例存在（含转义后的单个元素数组）",
      "Minimal correct example" in desc and r'[\"Rendering visualization\"]' in desc)
check("失败原文与自纠指令存在（不得原样重试）",
      "loading_messages must contain at least one message." in desc
      and "do NOT repeat the same call" in desc)
check("类型仍是 string（客户端 schema 语义不变，只改描述）", lm.get("type") == "string")
check("required 仍含 loading_messages",
      "loading_messages" in sw[0]["function"]["parameters"]["required"])
check("幂等：第二次调用不再改写（rewritten 为空）",
      P.harden_tool_schemas(h_raw)[1]["rewritten"] == [])
check("确定性：同一输入两次调用逐字节相同", P.harden_tool_schemas(TOOLS_BODY)[0] == h_raw)
_cmp = lambda a, b: json.dumps(a, ensure_ascii=False) == json.dumps(b, ensure_ascii=False)
_raw_props = [t for t in RAW["tools"]
              if t.get("function", {}).get("name") == "show_widget"][0]["function"]["parameters"]["properties"]
check("只有 loading_messages 一处被改（widget_code 描述逐字节不变）",
      _cmp(sw[0]["function"]["parameters"]["properties"]["widget_code"],
           _raw_props["widget_code"]))
check("无 tools / 非 JSON 请求体：原样返回、不抛异常",
      P.harden_tool_schemas(SMALL_BODY)[0] == SMALL_BODY
      and P.harden_tool_schemas(b"{oops")[0] == b"{oops"
      and P.harden_tool_schemas(SMALL_BODY)[1]["rewritten"] == [])
check("其他工具（非 show_widget）未被改写（抽查 3 个工具逐字节相同）",
      all(_cmp(a, b) for a, b in zip(
          [t for t in hb["tools"] if t.get("function", {}).get("name") != "show_widget"][:3],
          [t for t in RAW["tools"] if t.get("function", {}).get("name") != "show_widget"][:3])))

# ---------------------------------------------------------------- 语义校验器
print("\nF1 semantic validator（可解析为数组 / 长度 1–4 / 元素为字符串）")
cases = [
    ('["a"]', True, "json_string"),
    ('["a","b","c","d"]', True, "json_string"),
    (["a"], True, "bare_array"),
    ("", False, None),
    ("[]", False, None),
    ("[  ]", False, None),
    ("[1,2]", False, None),
    ('"abc"', False, None),
    ('["a","b","c","d","e"]', False, None),
    (["a", ""], False, None),
    (None, False, None),
    ({"a": 1}, False, None),
    ("not json", False, None),
]
bad = []
for val, want_ok, want_how in cases:
    ok, reason, _arr = P.validate_loading_messages(val)
    if ok != want_ok or (want_how and reason != want_how):
        bad.append((str(val), ok, reason))
check("13 个语义用例（有效/空串/空数组/裸数组/非字符串元素/超长/非数组/缺失）全部判定正确",
      not bad, bad)
ok, reason, arr = P.validate_loading_messages('["x","y"]')
check("失败原因给出精确原因（用于自纠），成功时给出解析方式",
      ok and reason == "json_string" and arr == ["x", "y"]
      and P.validate_loading_messages("")[1] == "空字符串"
      and "不是合法 JSON" in P.validate_loading_messages("oops")[1])

# ---------------------------------------------------------------- F1 观测量：历史审计
print("\nF1 历史审计观测量（真实抓包：P05 的现场证据）")
audit = P.inspect_tool_arg_history(RAW["messages"])
check("真实抓包里 show_widget 调用被计数（calls>0）", audit["calls"] > 0, audit)
check("真实抓包里存在工具失败记录（tool_failures>0）", audit["tool_failures"] > 0, audit)
check("真实抓包能识别同一错误重复：repeated_identical_error 非空且指向 loading_messages",
      bool(audit["repeated_identical_error"])
      and any("loading_messages" in m for m in audit["repeated_identical_error"]), audit)
check("合法 + 不合法 == 调用总数（计数自洽）",
      audit["valid"] + audit["invalid"] == audit["calls"])
synthetic = [
    {"role": "assistant", "tool_calls": [{"function": {
        "name": "show_widget", "arguments": json.dumps({"loading_messages": ""})}}]},
    {"role": "tool", "content": json.dumps({"success": False, "message": "E1"})},
    {"role": "tool", "content": json.dumps({"success": False, "message": "E1"})},
    {"role": "assistant", "tool_calls": [{"function": {
        "name": "show_widget",
        "arguments": json.dumps({"loading_messages": '["ok"]'})}}]},
]
a2 = P.inspect_tool_arg_history(synthetic)
check("合成夹具：不合法 1 / 合法 1，且重复错误被识别",
      a2["invalid"] == 1 and a2["valid"] == 1
      and a2["repeated_identical_error"] == ["E1"], a2)
a3 = P.inspect_tool_arg_history(synthetic[:2])
check("只出现一次的错误不算重复", a3["repeated_identical_error"] == [], a3)
check("arguments 不是合法 JSON 时计为不合法且不抛异常",
      P.inspect_tool_arg_history([{"role": "assistant", "tool_calls": [
          {"function": {"name": "show_widget", "arguments": "{broken"}}]}])["invalid"] == 1)
check("tool_arg_audit：无工具调用历史的请求返回 None（日志不膨胀）",
      P.tool_arg_audit(TOOLS_BODY) is None)
check("tool_arg_audit：真实抓包（含历史）返回审计结构",
      isinstance(P.tool_arg_audit(json.dumps(RAW, ensure_ascii=False).encode("utf-8")), dict))

# ---------------------------------------------------------------- F4 策略块
print("\nF4 工具错误恢复策略块")
P.CFG["tools"] = {"schema_hardening": True, "error_policy": True}
p_raw, p_note, p_chars = P.apply_tool_error_policy(TOOLS_BODY)
pb = json.loads(p_raw.decode("utf-8"))
sys_txt = pb["messages"][0]["content"]
check("带 tools 的请求被并入策略块（说明非空、字符数>0）", bool(p_note) and p_chars > 0)
check("策略块含同一错误连续两次不得原样重试与有副作用操作不得重复",
      "SAME error twice" in sys_txt and "never resend the identical call" in sys_txt
      and "side effects" in sys_txt and "Never blindly repeat" in sys_txt)
check("策略块是尾部追加：原 system 文本是改写后的前缀（不破坏已缓存前缀）",
      sys_txt.startswith("SYS") and sys_txt == "SYS" + P.TOOL_POLICY_BLOCK)
check("幂等：第二次调用不再改写（不会叠加多个策略块）",
      P.apply_tool_error_policy(p_raw)[1] is None
      and json.loads(P.apply_tool_error_policy(p_raw)[0].decode("utf-8"))["messages"][0]
      ["content"].count("tool-error recovery policy") == 1)
check("不带 tools 的请求不改写（原样字节返回）",
      P.apply_tool_error_policy(SMALL_BODY)[0] == SMALL_BODY
      and P.apply_tool_error_policy(SMALL_BODY)[1] is None)
P.CFG["tools"]["error_policy"] = False
check("config.tools.error_policy=false 时整体关闭",
      P.apply_tool_error_policy(TOOLS_BODY)[1] is None)
P.CFG["tools"]["error_policy"] = True
multi = json.dumps({"messages": [{"role": "system", "content": [{"type": "text", "text": "S"}]},
                                 {"role": "user", "content": "x"}],
                    "tools": [{"type": "function", "function": {"name": "t"}}]},
                   ensure_ascii=False).encode("utf-8")
check("system content 是多模态数组时跳过（不猜、不抛异常）",
      P.apply_tool_error_policy(multi)[0] == multi
      and P.apply_tool_error_policy(multi)[1] is None)
check("策略块文本本身是常量（长度>200，不含任何请求内容）",
      len(P.TOOL_POLICY_BLOCK) > 200 and "SYS" not in P.TOOL_POLICY_BLOCK)

# ---------------------------------------------------------------- 整条管线
print("\n整条管线（瘦身 -> 契约加固 -> 策略块 -> 思考档位）")


def pipeline(b):
    b, _s, _sd = P.slim_tools(b)
    b, _h = P.harden_tool_schemas(b)
    b, _p, _pc = P.apply_tool_error_policy(b)
    b, _n, _src, _ap = P.apply_thinking_policy(b)
    return b


body = pipeline(TOOLS_BODY)
final = json.loads(body.decode("utf-8"))
check("管线输出仍是合法 JSON 且 tools/messages 结构完好",
      isinstance(final.get("tools"), list) and len(final["tools"]) == len(RAW["tools"])
      and final["messages"][0]["content"].startswith("SYS"))
check("管线后工具体契约仍在（加固未被后续步骤回退）",
      'field name exactly "loading_messages"' in
      [t for t in final["tools"] if t["function"]["name"] == "show_widget"][0]
      ["function"]["parameters"]["properties"]["loading_messages"]["description"])
check("管线确定性：同输入两次跑完整管线逐字节相同", pipeline(TOOLS_BODY) == body)

# ---------------------------------------------------------------- 配置与启动器
print("\n配置与启动器（唯一权威来源一致性）")
cfg = json.load(open(CONFIG, encoding="utf-8-sig"))
sl = cfg.get("slimming") or {}
check("config.slimming：locations=true（保留零代价项）", sl.get("locations") is True)
check("config.slimming：deferred_tools=false（恢复 deferred 工具名册，P09）",
      sl.get("deferred_tools") is False)
check("config.slimming：subagents=false（恢复子代理类型名册，P09）",
      sl.get("subagents") is False)
tl = cfg.get("tools") or {}
check("config.tools：schema_hardening / error_policy 均为 true 且有 _note",
      tl.get("schema_hardening") is True and tl.get("error_policy") is True
      and isinstance(tl.get("_note"), str) and len(tl["_note"]) > 50)
P2 = load_proxy()
ok = P2.load_runtime(CONFIG)
check("代理 load_runtime 读入三项瘦身与两项 tools 开关",
      ok and P2.CFG["slimming"]["locations"] is True
      and P2.CFG["slimming"]["deferred_tools"] is False
      and P2.CFG["slimming"]["subagents"] is False
      and P2.CFG["tools"]["schema_hardening"] is True
      and P2.CFG["tools"]["error_policy"] is True, P2.CFG)
P2.ARGS = SimpleNamespace(effort=None, keep_location=False, upstream=8081)
check("真实配置下 keep_location() 为假（瘦身仍生效，只是逐项）", P2.keep_location() is False)

lau = open(LAUNCHER, encoding="utf-8").read()
check("启动器横幅不再有过期文案（阶段 D 验证前只登记）", "阶段 D 验证前只登记" not in lau)
check("启动器不再声称代理只支持全开/全关", "只支持全开/全关" not in lau)
check("启动器横幅含逐项瘦身说明与工具体两行（与代理实际行为一致）",
      "阶段 F 起代理按配置逐项生效" in lau and "错误恢复策略块" in lau
      and "deferred/subagent=false 表示保留完整名册" in lau)
pl = open(PROXY, encoding="utf-8").read()
check("代理启动横幅含逐项瘦身与工具体说明（在线可见，可核验）",
      "阶段 F 起各自独立" in pl and "契约加固" in pl)

spec = importlib.util.spec_from_file_location("launcher_f", LAUNCHER)
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)


def args_for(loc, dft, sub):
    c = {"python": sys.executable, "proxy": {"script": "P", "port": 8080, "upstream_port": 8081},
         "thinking": {"default_effort": "medium"},
         "slimming": {"locations": loc, "deferred_tools": dft, "subagents": sub}}
    return L.proxy_args(c)


check("proxy_args：逐项配置（开/关/关）不传 --keep-location（代理自己按 config 逐项生效）",
      "--keep-location" not in args_for(True, False, False))
check("proxy_args：三项全 false 才传 --keep-location（A/B 对照）",
      "--keep-location" in args_for(False, False, False))
check("proxy_args：三项全开也不传 --keep-location", "--keep-location" not in args_for(True, True, True))

print("\n" + "=" * 70)
print("阶段 F 离线验收：PASS %d / FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项：")
    for f in FAIL:
        print("  - " + f)
print("=" * 70)
sys.exit(1 if FAIL else 0)