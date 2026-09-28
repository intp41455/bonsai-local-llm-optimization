# -*- coding: utf-8 -*-
r"""阶段 E1：输入空间预算精确核算（不启动服务、不做推理）

方案 §7/E1 要求：优先用当前 server 的 /apply-template 与 /tokenize，核算【完成代理变换后
的实际输入】，包括 messages、tools、模板包装；不凭字符数估算精确 token；记录核算本身耗时。

本脚本做三件事：
  1) 取最新一份真实 Agent 抓包（capture\req_*.json），依次算出三个口径的精确输入 token：
       A0 客户端原样（未瘦身）
       A1 A0 + 请求瘦身（strip_locations，与 --keep-location 对照）
       A2 A1 + 思考策略（apply_thinking_policy）＝ 服务端实际收到的输入
     三个口径都经 /apply-template 渲染成 prompt 再 /tokenize，口径一致、可直接相减。
  2) 对 A2 做分段核算（tools 固定开销 / system 固定开销 / 历史开销），
     用“同一模板下移除该段后的差值”计算，避免字符估算。
  3) 按方案 §7 预算规则出判定：
        input + 计划总生成 + 上下文余量 <= 有效上下文窗口
     超预算即报“生成前发现”，本脚本只报判定，不改请求（不静默裁剪）。

只用 /apply-template 与 /tokenize，二者都不走推理槽位；为稳妥仍在开始时查一次 /slots，
后端忙则等待。
"""
import http.client
import importlib.util
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

DEMO = r"D:\Bonsai-demo"
PROXY = os.path.join(DEMO, "proxy", "bonsai_proxy.py")
CONFIG = os.path.join(DEMO, "config", "bonsai-agent.json")
OPT = os.path.join(DEMO, "optimization", "20260927_165311")
RESULTS = os.path.join(OPT, "results")
UPSTREAM = ("127.0.0.1", 8081)


def load_proxy():
    spec = importlib.util.spec_from_file_location("bonsai_proxy_e", PROXY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def post(path, obj, timeout=600.0):
    t0 = time.monotonic()
    c = http.client.HTTPConnection(UPSTREAM[0], UPSTREAM[1], timeout=float(timeout))
    try:
        c.request("POST", path,
                  body=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
        r = c.getresponse()
        raw = r.read()
        body = json.loads(raw.decode("utf-8", "ignore")) if raw.strip() else None
        return r.status, body, round((time.monotonic() - t0) * 1000.0, 1)
    finally:
        try:
            c.close()
        except Exception:
            pass


def get(path, timeout=10.0):
    c = http.client.HTTPConnection(UPSTREAM[0], UPSTREAM[1], timeout=float(timeout))
    try:
        c.request("GET", path)
        r = c.getresponse()
        raw = r.read()
        return json.loads(raw.decode("utf-8", "ignore")) if raw.strip() else None
    except Exception:
        return None
    finally:
        try:
            c.close()
        except Exception:
            pass


def n_tokens(o):
    if isinstance(o, list):
        return len(o)
    if isinstance(o, dict):
        if isinstance(o.get("tokens"), list):
            return len(o["tokens"])
        if isinstance(o.get("content"), list):
            return len(o["content"])
    return None


def apply_template(body):
    st, o, ms = post("/apply-template", body)
    if st != 200 or not isinstance(o, dict) or "prompt" not in o:
        raise RuntimeError("/apply-template 失败 status=%s body=%r" % (st, str(o)[:200]))
    return o["prompt"], ms


def count(text, add_special=False):
    st, o, ms = post("/tokenize", {"content": text, "add_special": add_special,
                                   "parse_special": True})
    if st != 200:
        raise RuntimeError("/tokenize 失败 status=%s body=%r" % (st, str(o)[:200]))
    return n_tokens(o), ms


def prompt_tokens(body, add_special=False):
    """渲染 + 计数，返回 (tokens, apply_ms, tokenize_ms)。"""
    p, t1 = apply_template(body)
    n, t2 = count(p, add_special)
    return n, t1, t2


def wait_idle(timeout_s=120.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        s = get("/slots")
        busy = None
        if isinstance(s, list):
            busy = any(isinstance(x, dict) and x.get("is_processing") for x in s)
        elif isinstance(s, dict):
            busy = bool(s.get("is_processing"))
        if busy is False:
            return True
        time.sleep(1.0)
    return False


def props_n_ctx(p):
    for k in ("n_ctx", "default_n_ctx"):
        if isinstance(p, dict) and isinstance(p.get(k), int):
            return p[k]
    d = (p or {}).get("default_generation_settings") or {}
    if isinstance(d, dict):
        for k in ("n_ctx", "default_n_ctx"):
            if isinstance(d.get(k), int):
                return d[k]
        pr = d.get("params") or {}
        if isinstance(pr, dict) and isinstance(pr.get("n_ctx"), int):
            return pr["n_ctx"]
    return None


def strip_for_variant(body, mode):
    """构造分段核算用的变体（只读检查，不改原始请求）。"""
    d = json.loads(json.dumps(body))
    if mode == "full":
        return d
    if mode == "no_tools":
        d.pop("tools", None)
        d.pop("tool_choice", None)
        return d
    if mode == "no_system":
        d["messages"] = [m for m in d.get("messages", [])
                         if m.get("role") != "system"]
        return d
    if mode == "last_only":
        msgs = d.get("messages", [])
        keep = [m for m in msgs if m.get("role") == "system"]
        tail = [m for m in msgs if m.get("role") != "system"]
        d["messages"] = keep + tail[-1:]
        return d
    raise ValueError(mode)


def main():
    P = load_proxy()
    cfg = json.load(open(CONFIG, encoding="utf-8-sig"))
    bu = cfg.get("budget") or {}
    plan_gen = int(bu.get("request_max_tokens") or 0)
    reserve = int(bu.get("context_reserve_tokens") or 0)

    out = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "proxy_sha256": None,
           "config_hash": None, "n_ctx": None, "budget_cfg": bu,
           "capture": None, "variants": {}, "breakdown": {}, "budget": {},
           "timing_ms": {}}

    import hashlib
    out["proxy_sha256"] = hashlib.sha256(open(PROXY, "rb").read()).hexdigest()
    out["config_hash"] = getattr(P, "CONFIG_HASH", None)

    props = get("/props")
    ctx = props_n_ctx(props)
    out["n_ctx"] = ctx
    print("[服务] n_ctx=%s  build_info=%s" % (ctx, (props or {}).get("build_info")))
    if ctx is None:
        print("[服务] !! 取不到 n_ctx，预算判定将用配置里的 65536 兜底并标注来源")

    idle = wait_idle(120.0)
    print("[服务] /slots 空闲=%s（/apply-template 与 /tokenize 不走推理槽位，仅此处确认不抢任务）"
          % idle)

    cap = P.pick_newest_capture()
    if not cap or not os.path.exists(cap):
        print("[抓包] 没有可用的大请求，终止。")
        return 2
    out["capture"] = {"path": cap, "chars": os.path.getsize(cap)}
    raw = open(cap, "rb").read()
    print("[抓包] %s  %.1f KB" % (os.path.basename(cap), len(raw) / 1024.0))

    # ---- 三个口径 ----
    body0 = json.loads(raw.decode("utf-8", "ignore"))
    slim_raw, saved_chars, _slim_detail = P.slim_tools(raw)
    body1 = json.loads(slim_raw.decode("utf-8", "ignore"))
    P.ARGS = type("A", (), {"effort": "medium", "keep_location": False, "upstream": 8081})()
    P.RAW_CFG = cfg
    body2_raw, note, src, applied = P.apply_thinking_policy(slim_raw)
    body2 = json.loads(body2_raw.decode("utf-8", "ignore"))

    t_all0 = time.monotonic()
    for name, body in (("A0_client_raw", body0), ("A1_slimmed", body1), ("A2_final", body2)):
        n_false, t1, t2 = prompt_tokens(body, add_special=False)
        n_true, t3, t4 = prompt_tokens(body, add_special=True)
        out["variants"][name] = {
            "prompt_tokens_add_special_false": n_false,
            "prompt_tokens_add_special_true": n_true,
            "apply_template_ms": t1, "tokenize_ms": t2,
            "prompt_chars": len(json.dumps(body, ensure_ascii=False)),
        }
        print("  [%s] input=%s tok(no-bos) / %s tok(bos)  apply=%.0fms tok=%.0fms"
              % (name, n_false, n_true, t1, t2))

    a0 = out["variants"]["A0_client_raw"]["prompt_tokens_add_special_true"]
    a1 = out["variants"]["A1_slimmed"]["prompt_tokens_add_special_true"]
    a2 = out["variants"]["A2_final"]["prompt_tokens_add_special_true"]
    out["slimming"] = {"saved_chars": saved_chars, "saved_tokens": a0 - a1,
                       "saved_pct": round(100.0 * (a0 - a1) / a0, 2) if a0 else None,
                       "note": note, "effort_source": src, "effort_applied": applied}
    print("  [瘦身] 省 %d tok（%.2f%%，字符层面省 %d）"
          % (a0 - a1, out["slimming"]["saved_pct"] or 0.0, saved_chars))

    # ---- 分段核算（A2 口径，同模板差值法）----
    base = out["variants"]["A2_final"]["prompt_tokens_add_special_true"]
    seg = {}
    for mode, label in (("no_tools", "tools_fixed"),
                        ("no_system", "system_fixed"),
                        ("last_only", "history")):
        v = strip_for_variant(body2, mode)
        try:
            n, t1, t2 = prompt_tokens(v, add_special=True)
        except Exception as e:
            seg[label] = {"error": repr(e)}
            print("  [分段] %s 失败 %r" % (mode, e))
            continue
        seg[label] = {"tokens_without": n, "delta_tokens": base - n,
                      "apply_ms": t1, "tokenize_ms": t2}
        print("  [分段] 去掉 %-10s 后 = %d tok，该段占 %d tok" % (mode, n, base - n))
    out["breakdown"] = {"base_tokens": base, "segments": seg}
    fixed = (seg.get("tools_fixed", {}).get("delta_tokens") or 0) + \
            (seg.get("system_fixed", {}).get("delta_tokens") or 0)
    out["breakdown"]["fixed_overhead_tools_plus_system"] = fixed
    out["breakdown"]["fixed_overhead_pct"] = round(100.0 * fixed / base, 2) if base else None
    print("  [固定开销] tools+system = %d tok（占 %.1f%%）"
          % (fixed, out["breakdown"]["fixed_overhead_pct"] or 0.0))

    # ---- 预算判定（方案 §7 规则）----
    win = ctx or 65536
    need = a2 + plan_gen + reserve
    out["budget"] = {
        "n_ctx": win, "n_ctx_source": "server /props" if ctx else "配置兜底 65536",
        "input_tokens": a2,
        "planned_total_generation": plan_gen,
        "context_reserve": reserve,
        "required": need,
        "headroom_tokens": win - need,
        "verdict": "超预算(生成前应拒绝/告警)" if need > win else "在预算内",
        "input_pct_of_window": round(100.0 * a2 / win, 2),
    }
    # 输入单独是否已逼近窗口
    out["budget"]["input_alone_pct"] = round(100.0 * a2 / win, 2)
    # 目标区间（方案 E3：普通任务 8k-24k）
    out["budget"]["target_range_tokens"] = [8192, 24576]
    out["budget"]["input_vs_target"] = ("高于目标上限 24k" if a2 > 24576
                                        else ("低于目标下限 8k" if a2 < 8192 else "在 8k-24k 目标区间"))
    print("\n[预算] 输入 %d + 计划生成 %d + 余量 %d = %d  vs 窗口 %d  -> %s（余 %+d tok）"
          % (a2, plan_gen, reserve, need, win, out["budget"]["verdict"], win - need))
    print("[预算] 输入仅占窗口 %.1f%%，%s" % (out["budget"]["input_pct_of_window"],
                                        out["budget"]["input_vs_target"]))

    out["timing_ms"]["total"] = round((time.monotonic() - t_all0) * 1000.0, 1)
    print("[耗时] 本次核算共 %.0f ms（含 %d 次 /apply-template + %d 次 /tokenize）"
          % (out["timing_ms"]["total"],
             3 + len(seg), 6 + 2 * len(seg)))

    os.makedirs(RESULTS, exist_ok=True)
    jp = os.path.join(RESULTS, "stage_e_probe.json")
    tp = os.path.join(RESULTS, "stage_e_probe.txt")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    lines = [
        "阶段 E1 输入空间预算精确核算",
        "时间: %s" % out["started"],
        "代理 sha256: %s" % out["proxy_sha256"][:16],
        "抓包: %s  (%.1f KB)" % (os.path.basename(cap), len(raw) / 1024.0),
        "n_ctx: %s (%s)" % (out["budget"]["n_ctx"], out["budget"]["n_ctx_source"]),
        "",
        "口径            add_special=false   add_special=true",
    ]
    for name in ("A0_client_raw", "A1_slimmed", "A2_final"):
        v = out["variants"][name]
        lines.append("  %-14s %10d %18d" % (name, v["prompt_tokens_add_special_false"],
                                             v["prompt_tokens_add_special_true"]))
    lines += [
        "",
        "瘦身省 token: %d（%.2f%%，字符层面 %d）  来源=%s  注入=%s"
        % (out["slimming"]["saved_tokens"], out["slimming"]["saved_pct"] or 0.0,
           out["slimming"]["saved_chars"], out["slimming"]["effort_source"],
           out["slimming"]["effort_applied"]),
        "",
        "分段核算（A2 口径，同模板差值法）:",
        "  总输入            %6d tok" % base,
    ]
    for label, zh in (("tools_fixed", "tools 固定开销"), ("system_fixed", "system 固定开销"),
                      ("history", "历史消息")):
        s = seg.get(label) or {}
        lines.append("  %-16s %6s tok" % (zh, s.get("delta_tokens", "n/a")))
    lines += [
        "  固定开销合计      %6d tok（占 %.1f%%）"
        % (fixed, out["breakdown"]["fixed_overhead_pct"] or 0.0),
        "",
        "预算判定: 输入 %d + 计划生成 %d + 余量 %d = %d  vs 窗口 %d" % (
            a2, plan_gen, reserve, need, win),
        "  -> %s（余 %+d tok）" % (out["budget"]["verdict"], win - need),
        "  输入占窗口 %.1f%%；%s" % (out["budget"]["input_pct_of_window"],
                                out["budget"]["input_vs_target"]),
        "",
        "核算耗时: %.0f ms" % out["timing_ms"]["total"],
    ]
    with open(tp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n已写出: %s\n        %s" % (jp, tp))
    return 0


if __name__ == "__main__":
    sys.exit(main())