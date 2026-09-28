# -*- coding: utf-8 -*-
r"""阶段 D 离线验收测试（不启动服务、不加载模型、不发真实推理）

覆盖方案 §6 / §D2–D3 中"代理侧"可离线验证的部分：
  D2-1 优先级：显式请求参数 > 代理配置档 > 服务默认；客户端已指定一律不覆盖
  D2-2 识别来源：顶层 reasoning_effort / chat_template_kwargs.reasoning_effort / .enable_thinking
  D2-3 档位归一：off|none|false -> enable_thinking=false；xhigh|medium|low -> reasoning_effort；
                 其它值不注入并标记 invalid（模板会对非法档位返回 500，代理不能把 none 传下去）
  D2-4 带请求级预算的请求不再被注入档位（避免打断预算语义）
  D3-1 预算注入默认关闭（config.budget.policy 两项 false）
  D3-2 逐项打开后按 policy 注入 max_tokens / reasoning_budget_tokens
  D3-3 绝不覆盖客户端已给的 max_tokens / 思考预算；关闭思考时不再注入思考预算
  C4'  requests.jsonl 记录新增字段：effort_source / effort_effective / budget_applied

用法：
    python stage_d_tests.py                                    # 测已部署的代理
    set BONSAI_PROXY_PATH=<文件> && python stage_d_tests.py     # 测暂存副本（部署前）
"""
import importlib.util
import json
import os
import sys
from types import SimpleNamespace

PROXY = os.environ.get("BONSAI_PROXY_PATH") or r"D:\Bonsai-demo\proxy\bonsai_proxy.py"
PASS, FAIL = [], []
sys.stdout.reconfigure(encoding="utf-8")


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("  <- " + str(detail)) if (detail and not cond) else ""))


def load(path):
    spec = importlib.util.spec_from_file_location("bonsai_proxy_dut", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def call(P, effort, body, policy=None, budget=None, force_budget=None):
    """按给定配置档位与预算策略调用 apply_thinking_policy。"""
    P.ARGS = SimpleNamespace(effort=effort, keep_location=True, upstream=8081)
    cfg = dict(budget or {"request_max_tokens": 8192, "thinking_budget_tokens": 2048})
    cfg["policy"] = dict(policy or {"apply_request_max_tokens": False,
                                   "apply_thinking_budget": False})
    if force_budget:
        cfg.update(force_budget)
    P.RAW_CFG = {"budget": cfg}
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    out, note, src, applied = P.apply_thinking_policy(raw)
    return json.loads(out.decode("utf-8")), note, src, (applied or {})


CHAT = {"messages": [{"role": "user", "content": "hi"}]}


def main():
    P = load(PROXY)
    print("== 阶段 D 离线测试：%s ==" % PROXY)

    # ---------- D2-3 代理档位注入与归一 ----------
    d, note, src, ap = call(P, "medium", json.loads(json.dumps(CHAT)))
    check("D2 无客户端意图 + effort=medium -> 注入 reasoning_effort=medium",
          d.get("chat_template_kwargs", {}).get("reasoning_effort") == "medium"
          and src == "proxy_profile" and ap.get("reasoning_effort") == "medium", (d, src, ap))

    d, note, src, ap = call(P, "xhigh", json.loads(json.dumps(CHAT)))
    check("D2 effort=xhigh -> 注入 reasoning_effort=xhigh",
          d.get("chat_template_kwargs", {}).get("reasoning_effort") == "xhigh", d)

    d, note, src, ap = call(P, "off", json.loads(json.dumps(CHAT)))
    check("D2 effort=off -> 注入 enable_thinking=false",
          d.get("chat_template_kwargs", {}).get("enable_thinking") is False
          and "reasoning_effort" not in d.get("chat_template_kwargs", {}), d)

    d, note, src, ap = call(P, "none", json.loads(json.dumps(CHAT)))
    check("D2 effort=none -> 归一成 enable_thinking=false（绝不把 none 当档位传模板）",
          d.get("chat_template_kwargs", {}).get("enable_thinking") is False
          and d.get("chat_template_kwargs", {}).get("reasoning_effort") is None, d)

    d, note, src, ap = call(P, "high", json.loads(json.dumps(CHAT)))
    check("D2 effort=high（模板不支持的档位）-> 不注入且标记 invalid",
          d == CHAT and src == "invalid" and note and "跳过注入" in note, (d, src, note))

    # ---------- D2-1 / D2-2 优先级：客户端已指定不覆盖 ----------
    b = json.loads(json.dumps(CHAT)); b["reasoning_effort"] = "low"
    d, note, src, ap = call(P, "xhigh", b)
    check("D2 顶层 reasoning_effort=low -> 不覆盖（src=client，body 原样）",
          d == b and src == "client", (d, src))

    b = json.loads(json.dumps(CHAT)); b["chat_template_kwargs"] = {"reasoning_effort": "low"}
    d, note, src, ap = call(P, "xhigh", b)
    check("D2 模板参数 reasoning_effort=low -> 不覆盖",
          d == b and src == "client", (d, src))

    b = json.loads(json.dumps(CHAT)); b["chat_template_kwargs"] = {"enable_thinking": False}
    d, note, src, ap = call(P, "xhigh", b)
    check("D2 模板参数 enable_thinking=false -> 不覆盖（用户要关思考）",
          d == b and src == "client", (d, src))

    b = json.loads(json.dumps(CHAT)); b["reasoning_budget_tokens"] = 64
    d, note, src, ap = call(P, "medium", b)
    check("D2 客户端自带 reasoning_budget_tokens -> 不注入档位（src=client_budget）",
          d == b and src == "client_budget", (d, src))

    b = json.loads(json.dumps(CHAT)); b["thinking_budget_tokens"] = 64
    d, note, src, ap = call(P, "medium", b)
    check("D2 客户端用别名 thinking_budget_tokens -> 同样不注入档位",
          d == b and src == "client_budget", (d, src))

    d, note, src, ap = call(P, None, json.loads(json.dumps(CHAT)))
    check("D2 代理未配置档位（effort=None）-> 不动 body",
          d == CHAT and src == "none" and note is None, (d, src, note))

    # ---------- 非对话请求 ----------
    out, note, src, ap = P.apply_thinking_policy(b"not json at all")
    check("D2 非 JSON body -> 原样返回（src=unparsed）",
          out == b"not json at all" and src == "unparsed", (out, src))

    out, note, src, ap = P.apply_thinking_policy(b'{"model":"m","prompt":"x"}')
    check("D2 非对话请求（无 messages）-> 原样返回（src=not_chat）",
          out == b'{"model":"m","prompt":"x"}' and src == "not_chat", (out, src))

    # ---------- D3-1 预算注入默认关闭 ----------
    d, note, src, ap = call(P, "medium", json.loads(json.dumps(CHAT)))
    check("D3 policy 两项=false -> 不注入 max_tokens / reasoning_budget_tokens",
          "max_tokens" not in d and "reasoning_budget_tokens" not in d
          and "max_tokens" not in ap and "reasoning_budget_tokens" not in ap, (d, ap))

    # ---------- D3-2 逐项打开 ----------
    d, note, src, ap = call(P, "medium", json.loads(json.dumps(CHAT)),
                            policy={"apply_request_max_tokens": True,
                                    "apply_thinking_budget": False})
    check("D3 只开 max_tokens -> 注入 8192，仍不注入思考预算",
          d.get("max_tokens") == 8192 and "reasoning_budget_tokens" not in d, (d, ap))

    d, note, src, ap = call(P, "medium", json.loads(json.dumps(CHAT)),
                            policy={"apply_request_max_tokens": False,
                                    "apply_thinking_budget": True})
    check("D3 只开思考预算 -> 注入 reasoning_budget_tokens=2048",
          d.get("reasoning_budget_tokens") == 2048 and "max_tokens" not in d, (d, ap))

    d, note, src, ap = call(P, "medium", json.loads(json.dumps(CHAT)),
                            policy={"apply_request_max_tokens": True,
                                    "apply_thinking_budget": True})
    check("D3 两项全开 -> 两个字段都注入",
          d.get("max_tokens") == 8192 and d.get("reasoning_budget_tokens") == 2048, (d, ap))

    # ---------- D3-3 不覆盖客户端 / 关闭思考时不注入 ----------
    b = json.loads(json.dumps(CHAT)); b["max_tokens"] = 100
    d, note, src, ap = call(P, "medium", b,
                            policy={"apply_request_max_tokens": True,
                                    "apply_thinking_budget": False})
    check("D3 客户端已给 max_tokens=100 -> 不覆盖",
          d.get("max_tokens") == 100, d)

    b = json.loads(json.dumps(CHAT)); b["chat_template_kwargs"] = {"enable_thinking": False}
    d, note, src, ap = call(P, "off", b,
                            policy={"apply_request_max_tokens": True,
                                    "apply_thinking_budget": True})
    check("D3 客户端已关思考 -> 不注入思考预算（仍可注入总生成预算）",
          "reasoning_budget_tokens" not in d and d.get("max_tokens") == 8192, (d, ap))

    d, note, src, ap = call(P, "off", json.loads(json.dumps(CHAT)),
                            policy={"apply_request_max_tokens": True,
                                    "apply_thinking_budget": True})
    check("D3 代理档位=off（关闭思考）-> 不注入思考预算",
          "reasoning_budget_tokens" not in d and d.get("max_tokens") == 8192, (d, ap))

    # ---------- C4' 请求日志字段 ----------
    rec = P.new_record("rid-test", "POST", "/v1/chat/completions", 0.0)
    check("C4' requests.jsonl 新增 effort_source/effort_effective/budget_applied",
          all(k in rec for k in ("effort_source", "effort_effective", "budget_applied")),
          sorted(rec.keys())[:6])

    # ---------- 旧接口不应残留 ----------
    check("D2 旧的 apply_effort 已不存在（避免两套逻辑并存）",
          not hasattr(P, "apply_effort"))

    print()
    print("通过 %d / 失败 %d" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  - " + f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())