"""真实工作流端到端验证：OpenAI 兼容接口 / 工具调用 / 流式 / 提示词层 A/B。

Phase A  接口与 Agent 能力
  A1  /v1/models                    别名与元信息
  A2  非流式 chat + 约束遵循          system prompt 硬约束是否被遵守
  A3  流式 SSE                       TTFT / chunk 数 / 拼装一致性
  A4  单工具调用                     tools -> tool_calls
  A5  多工具选择（真实 Agent 场景）   在 4 个工具里选对
  A6  多轮 messages                  携带历史 + 工具结果回灌

Phase B  提示词层 A/B（同一任务，只换提示词）
  B0  无 system                     baseline
  B1  极简 system
  B2  详细人设 system               约束：类型注解 + docstring + 错误处理
  B3  few-shot 注入                 在 user 消息里给样例
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"D:/Bonsai-demo")
BIN = ROOT / "dist" / "bonsai2-8gb-combo" / "bin"
MODEL = ROOT / "models" / "bonsai2-gguf" / "27B" / "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"

COMMON = [
    "-ngl", "99", "-fa", "on", "-np", "1", "-b", "2048", "-ub", "512",
    "-c", "32768",
    "-ctk", "q4_0", "-ctv", "q4_0",
    "--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
    "--spec-draft-depth-max", "4096",
    "-ctkd", "q4_0", "-ctvd", "q4_0",
    "--backend-sampling", "--jinja", "--metrics",
    "--alias", "bonsai-2-27b",
    "--temp", "1.0", "--top-p", "0.95", "--top-k", "20",
    "-n", "24576",
    "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
    "--reasoning-budget", "20480",
    "--reasoning-budget-message", "Now produce the complete answer.",
]


def kill() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    time.sleep(3)


def vram() -> int:
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10).stdout
        return int(o.strip().split("\n")[0])
    except Exception:
        return -1


def wait_ready(proc: subprocess.Popen, timeout: int = 420) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def req(path: str, payload: dict | None = None, timeout: int = 900, method: str = "POST"):
    data = json.dumps(payload).encode() if payload is not None else None
    r = urllib.request.Request(f"{BASE}{path}", data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def chat(messages, tools=None, n_predict=600, effort="medium", extra=None):
    """非流式 /v1/chat/completions，返回 (全文, timings, tool_calls, finish)"""
    payload = {
        "messages": messages, "n_predict": n_predict, "temperature": 0.0,
        "stream": False,
        "chat_template_kwargs": {"reasoning_effort": effort},
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    if extra:
        payload.update(extra)
    r = req("/v1/chat/completions", payload)
    ch = r["choices"][0]
    msg = ch.get("message", {})
    return (msg.get("content") or "",
            r.get("timings", {}) or {},
            msg.get("tool_calls") or [],
            ch.get("finish_reason"))


def stream_chat(messages, n_predict=300):
    """流式 SSE。返回 (TTFT, 总时长, chunk 数, 拼接文本)"""
    payload = {"messages": messages, "n_predict": n_predict, "temperature": 0.0,
               "stream": True, "chat_template_kwargs": {"reasoning_effort": "low"}}
    r = urllib.request.Request(f"{BASE}/v1/chat/completions",
                               data=json.dumps(payload).encode(),
                               headers={"Content-Type": "application/json"})
    t0 = time.time()
    ttft = None
    nchunk = 0
    buf = []
    with urllib.request.urlopen(r, timeout=900) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            body = line[5:].strip()
            if body == "[DONE]":
                break
            try:
                o = json.loads(body)
            except Exception:
                continue
            d = (o.get("choices") or [{}])[0].get("delta", {})
            c = d.get("content") or ""
            if c:
                if ttft is None:
                    ttft = time.time() - t0
                nchunk += 1
                buf.append(c)
    return ttft, time.time() - t0, nchunk, "".join(buf)


# ---------------------------------------------------------------- Phase A

TOOLS_SINGLE = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name, e.g. Beijing"}},
            "required": ["city"],
        },
    },
}]

TOOLS_MULTI = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read the contents of a local file",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "run_shell",
        "description": "Execute a shell command and return its output",
        "parameters": {"type": "object",
                       "properties": {"cmd": {"type": "string"}},
                       "required": ["cmd"]}}},
    {"type": "function", "function": {
        "name": "send_email",
        "description": "Send an email to a recipient",
        "parameters": {"type": "object",
                       "properties": {"to": {"type": "string"}, "subject": {"type": "string"}},
                       "required": ["to", "subject"]}}},
    {"type": "function", "function": {
        "name": "search_web",
        "description": "Search the web for a query",
        "parameters": {"type": "object",
                       "properties": {"q": {"type": "string"}},
                       "required": ["q"]}}},
]


def phase_a() -> dict:
    out = {}
    print(f"\n{'='*70}\n### Phase A  接口与 Agent 能力\n{'='*70}", flush=True)

    # A1
    try:
        m = req("/v1/models", method="GET")
        ids = [x.get("id") for x in m.get("data", [])]
        print(f"A1 /v1/models        -> {ids}", flush=True)
        out["A1_models"] = ids
    except Exception as e:
        print(f"A1 失败 {e}", flush=True)

    # A2 约束遵循：要求输出严格 JSON 且不含 markdown 围栏
    sysmsg = ("You are a strict API. Reply with a single JSON object and nothing else. "
              "No markdown fences, no explanation.")
    try:
        txt, t, tc, fin = chat(
            [{"role": "system", "content": sysmsg},
             {"role": "user", "content": "Extract: name=Alice, age=30, city=Shanghai. "
                                         "Return keys: name, age, city."}],
            n_predict=400, effort="low")
        strict = txt.strip()
        ok_json = False
        try:
            json.loads(strict)
            ok_json = True
        except Exception:
            pass
        ok_nofence = "```" not in strict
        print(f"A2 约束遵循          JSON 合法={ok_json}  无围栏={ok_nofence}  "
              f"dec={t.get('predicted_per_second',0):.1f} t/s  len={len(strict)}", flush=True)
        print(f"   输出: {strict[:150]}", flush=True)
        out["A2"] = {"json_ok": ok_json, "no_fence": ok_nofence,
                     "decode": t.get("predicted_per_second", 0), "text": strict[:400]}
    except Exception as e:
        print(f"A2 失败 {e}", flush=True)

    # A3 流式
    try:
        ttft, el, nch, text = stream_chat(
            [{"role": "user", "content": "Count from 1 to 20, one number per line."}],
            n_predict=200)
        print(f"A3 流式 SSE          TTFT={ttft:.2f}s  总={el:.2f}s  chunk={nch}  "
              f"tail={nch/el if el else 0:.1f}/s  len={len(text)}", flush=True)
        out["A3"] = {"ttft": ttft, "wall": el, "chunks": nch, "chars": len(text)}
    except Exception as e:
        print(f"A3 失败 {e}", flush=True)

    # A4 单工具
    try:
        txt, t, tc, fin = chat(
            [{"role": "user", "content": "What is the weather in Beijing right now?"}],
            tools=TOOLS_SINGLE, n_predict=400, effort="low")
        got = tc[0]["function"]["name"] if tc else None
        args = tc[0]["function"].get("arguments") if tc else None
        print(f"A4 单工具调用        tool_calls={got}  args={args}  finish={fin}", flush=True)
        out["A4"] = {"name": got, "args": args, "finish": fin, "text": txt[:200]}
    except Exception as e:
        print(f"A4 失败 {e}", flush=True)

    # A5 多工具选择 —— 真实 Agent 场景
    cases = [
        ("I want to know the latest news about the RTX 5090.", "search_web"),
        ("Show me what's inside D:/Bonsai-demo/README.md", "read_file"),
        ("Email alice@example.com about the meeting tomorrow.", "send_email"),
        ("List the largest files under /var/log", "run_shell"),
    ]
    hits = 0
    detail = []
    for q, want in cases:
        try:
            txt, t, tc, fin = chat([{"role": "user", "content": q}],
                                   tools=TOOLS_MULTI, n_predict=400, effort="low")
            got = tc[0]["function"]["name"] if tc else "(none)"
            ok = (got == want)
            hits += ok
            detail.append((q[:40], want, got, ok))
            print(f"    {'✓' if ok else '✗'} {q[:42]:44s} -> {got:12s} (期望 {want})", flush=True)
        except Exception as e:
            print(f"    ✗ {q[:40]} 失败 {str(e)[:60]}", flush=True)
            detail.append((q[:40], want, "ERROR", False))
    print(f"A5 多工具选择        {hits}/{len(cases)}", flush=True)
    out["A5"] = {"hits": hits, "total": len(cases), "detail": detail}

    # A6 多轮 + 工具结果回灌
    try:
        msgs = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the weather in Shanghai?"},
        ]
        txt, t, tc, fin = chat(msgs, tools=TOOLS_SINGLE, n_predict=300, effort="low")
        if tc:
            msgs.append({"role": "assistant", "content": None, "tool_calls": tc})
            msgs.append({"role": "tool", "tool_call_id": tc[0].get("id", "call_1"),
                         "content": '{"temp_c": 24, "condition": "clear"}'})
        else:
            msgs.append({"role": "assistant", "content": txt or ""})
            msgs.append({"role": "user", "content": "Pretend the weather is 24C and clear."})
        txt2, t2, tc2, fin2 = chat(msgs, n_predict=300, effort="low")
        ok = ("24" in txt2)
        print(f"A6 工具结果回灌      含24℃={ok}  dec={t2.get('predicted_per_second',0):.1f} t/s", flush=True)
        print(f"   回答: {txt2[:160]}", flush=True)
        out["A6"] = {"consumed": ok, "text": txt2[:400]}
    except Exception as e:
        print(f"A6 失败 {e}", flush=True)

    return out


# ---------------------------------------------------------------- Phase B

TASK = ("写一个 Python 函数 read_scores(path)，读取一个 CSV 文件（列：name,score），"
        "返回按 score 降序排序的 (name, score) 列表。")

SYSTEMS = {
    "B0-无system": None,
    "B1-极简": "You are a helpful assistant.",
    "B2-详细人设": (
        "You are a senior Python engineer with 15 years of experience. "
        "When writing code you MUST: (1) add full type annotations, "
        "(2) write a Google-style docstring, (3) handle errors with try/except and raise "
        "meaningful exceptions. Never omit any of the three."),
    "B3-fewshot注入": (
        "You are a senior Python engineer.\n\n"
        "Example of the required style:\n"
        "```python\n"
        "def add(a: int, b: int) -> int:\n"
        "    \"\"\"Add two integers.\n\n"
        "    Args:\n        a: first\n        b: second\n"
        "    Returns:\n        The sum.\n"
        "    \"\"\"\n"
        "    try:\n        return a + b\n"
        "    except TypeError as e:\n"
        "        raise ValueError('inputs must be ints') from e\n"
        "```\n"
        "Follow this style exactly: type annotations, docstring, try/except."),
}


def phase_b() -> dict:
    out = {}
    print(f"\n{'='*70}\n### Phase B  提示词层 A/B（同一任务，只换提示词）\n{'='*70}", flush=True)
    for name, sysmsg in SYSTEMS.items():
        msgs = []
        if sysmsg:
            msgs.append({"role": "system", "content": sysmsg})
        msgs.append({"role": "user", "content": TASK})
        try:
            txt, t, tc, fin = chat(msgs, n_predict=1200, effort="medium")
            has_ann = "->" in txt and (": " in txt or ":str" in txt or ": str" in txt)
            has_doc = '"""' in txt or "'''" in txt
            has_try = "try:" in txt
            code = txt
            print(f"{name:14s} dec={t.get('predicted_per_second',0):6.2f} t/s  "
                  f"tok={t.get('predicted_n',0):4d}  ch={len(code):5d}  "
                  f"类型注解={'Y' if has_ann else 'N'} docstring={'Y' if has_doc else 'N'} "
                  f"try={'Y' if has_try else 'N'}", flush=True)
            out[name] = {"decode": t.get("predicted_per_second", 0),
                         "tokens": t.get("predicted_n", 0), "chars": len(code),
                         "ann": has_ann, "doc": has_doc, "try": has_try,
                         "text": code[:1500]}
        except Exception as e:
            print(f"{name:14s} 失败 {str(e)[:80]}", flush=True)
    return out


def chat_full(messages, n_predict=4000, effort="medium", tools=None):
    """返回完整明细：正文 / 思考 token 数 / 思考字符数 / usage / timings"""
    payload = {
        "messages": messages, "n_predict": n_predict, "temperature": 0.0,
        "stream": False,
        "chat_template_kwargs": {"reasoning_effort": effort},
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    r = req("/v1/chat/completions", payload)
    ch = r["choices"][0]
    msg = ch.get("message", {})
    usage = r.get("usage", {}) or {}
    det = usage.get("completion_tokens_details") or {}
    think = msg.get("reasoning_content") or msg.get("reasoning") or ""
    return {
        "content": msg.get("content") or "",
        "think_tok": det.get("reasoning_tokens", 0),
        "out_tok": usage.get("completion_tokens", 0),
        "think_chars": len(think),
        "finish": ch.get("finish_reason"),
        "decode": (r.get("timings", {}) or {}).get("predicted_per_second", 0),
    }


PROBLEMS = [
    ("bat-ball", "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than "
                 "the ball. How much does the ball cost? Reply with only the amount.",
     ["0.05", "5 cent", "$.05"]),
    ("split-bill", "Alice pays twice what Bob pays. Bob pays 1.5 times what Carol pays. "
                   "The total is $143. Reply on one line: ANSWER: Alice=X Bob=Y Carol=Z",
     ["78", "39", "26"]),
    ("chick-rabbit", "A cage holds chickens and rabbits: 35 heads and 94 legs in total. "
                     "How many of each? Reply on one line: ANSWER: chickens=X rabbits=Y",
     ["23", "12"]),
]


def phase_c() -> dict:
    """思考档位 × 多步推理：看思考 token 开销与最终正确率"""
    out = {}
    print(f"\n{'='*70}\n### Phase C  思考档位 × 多步推理（可精确判定）\n{'='*70}", flush=True)
    print(f"{'档位':8s} {'题目':14s} {'思考tok':>8s} {'输出tok':>8s} {'墙钟':>7s} "
          f"{'命中':>6s}  finish", flush=True)
    for eff in ("low", "medium", "xhigh"):
        for pname, q, keys in PROBLEMS:
            try:
                t0 = time.time()
                d = chat_full([{"role": "user", "content": q}], n_predict=4000, effort=eff)
                el = time.time() - t0
                hit = sum(1 for k in keys if k in d["content"])
                print(f"{eff:8s} {pname:14s} {d['think_tok']:>8d} {d['out_tok']:>8d} "
                      f"{el:>6.1f}s {hit:>3d}/{len(keys)}  {d['finish']}", flush=True)
                out[f"{eff}-{pname}"] = {**d, "wall": el, "hit": hit,
                                         "total": len(keys)}
            except Exception as e:
                print(f"{eff:8s} {pname:14s} 失败 {str(e)[:60]}", flush=True)
    return out


# ---------------------------------------------------------------- Phase T
# 工具触发率 × system prompt：量化「写一句 system prompt」到底值多少

TOOL_QUERIES = [
    ("明确-read",   "Read the file C:/temp/notes.txt and show me its contents.",     "read_file"),
    ("明确-shell",  "Run the command `df -h` and report the output.",                "run_shell"),
    ("明确-search", "Search the web for the latest CUDA 13.1 release notes.",        "search_web"),
    ("含糊-email",  "Email alice@example.com about the meeting tomorrow.",           "send_email"),
    ("含糊-read",   "What's inside D:/Bonsai-demo/README.md?",                       "read_file"),
    ("含糊-news",   "I want to know the latest news about the RTX 5090.",            "search_web"),
]

TOOL_SYSTEMS = {
    "T0-无system": None,
    "T1-一句工具优先": (
        "You are a helpful assistant with access to tools. When a task can be "
        "accomplished with one of the available tools, ALWAYS call that tool "
        "instead of answering from memory or asking for confirmation."),
    "T2-工具规则三条": (
        "You are a helpful assistant with access to tools.\n"
        "Rules:\n"
        "1. If a task can be accomplished with a tool, ALWAYS call the tool. "
        "Never answer from memory.\n"
        "2. Fill every required argument from the user's message. Infer reasonable "
        "values (a recipient address, a file path) when the user implies them.\n"
        "3. Do not ask for confirmation; act."),
}


def phase_t() -> dict:
    out = {}
    print(f"\n{'='*70}\n### Phase T  工具触发率 × system prompt\n{'='*70}", flush=True)
    for sname, sysmsg in TOOL_SYSTEMS.items():
        hits = 0
        rows = []
        for qname, q, want in TOOL_QUERIES:
            msgs = []
            if sysmsg:
                msgs.append({"role": "system", "content": sysmsg})
            msgs.append({"role": "user", "content": q})
            try:
                txt, t, tc, fin = chat(msgs, tools=TOOLS_MULTI, n_predict=300,
                                       effort="low")
                got = tc[0]["function"]["name"] if tc else "(none)"
                ok = (got == want)
                hits += ok
                rows.append({"q": qname, "want": want, "got": got, "ok": ok})
                print(f"    {'✓' if ok else '✗'} {qname:14s} -> {got:12s} "
                      f"(期望 {want})", flush=True)
            except Exception as e:
                rows.append({"q": qname, "want": want, "got": "ERROR", "ok": False})
                print(f"    ✗ {qname:14s} 失败 {str(e)[:50]}", flush=True)
        print(f"  ==> {sname:16s} 触发率 {hits}/{len(TOOL_QUERIES)}", flush=True)
        out[sname] = {"hits": hits, "total": len(TOOL_QUERIES), "rows": rows}
    return out


CODE_TASK = ("Write a complete Python function `balanced(s: str) -> bool` that returns True "
             "iff the parentheses, brackets and braces in s are balanced. Include a 12-case "
             "pytest. Code only.")


def phase_d() -> dict:
    """编码任务 × 思考档位：官方说「medium 只有在 cap>=20k 时才追平教师」，在此验证"""
    import re as _re
    out = {}
    print(f"\n{'='*70}\n### Phase D  编码任务 × 思考档位（官方同款题）\n{'='*70}", flush=True)
    for eff in ("low", "medium"):
        try:
            t0 = time.time()
            d = chat_full([{"role": "user", "content": CODE_TASK}],
                          n_predict=6000, effort=eff)
            el = time.time() - t0
            body = d["content"]
            # 抽出代码块做编译检查
            blocks = _re.findall(r"```(?:python)?\s*(.*?)```", body, _re.S)
            src = "\n\n".join(blocks) if blocks else body
            try:
                compile(src, "<gen>", "exec")
                comp = True
            except SyntaxError as e:
                comp = False
            nfun = len(_re.findall(r"\bdef balanced\b", src))
            ntests = len(_re.findall(r"\bdef test_", src))
            print(f"  {eff:7s} 思考={d['think_chars']:5d}字  输出={d['out_tok']:5d}tok "
                  f"墙钟={el:5.1f}s  可编译={'Y' if comp else 'N'}  "
                  f"balanced定义={nfun}  测试函数={ntests}  finish={d['finish']}", flush=True)
            out[eff] = {**d, "wall": el, "compiles": comp, "n_balanced": nfun,
                        "n_tests": ntests}
        except Exception as e:
            print(f"  {eff:7s} 失败 {str(e)[:70]}", flush=True)
    return out


def main() -> None:
    phases = sys.argv[1:] or ["a", "b", "c"]
    log = open(ROOT / "wf_server.log", "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    cmd = [str(BIN / "llama-server.exe"), "-m", str(MODEL),
           "--host", "127.0.0.1", "--port", str(PORT)] + COMMON
    print(f"启动服务 (VRAM {vram()} MiB)...", flush=True)
    proc = subprocess.Popen(cmd, cwd=str(BIN), stdout=log, stderr=subprocess.STDOUT, env=env)
    result = {}
    try:
        if not wait_ready(proc):
            print("!! 服务未就绪", flush=True)
            return
        print(f"服务就绪，显存 {vram()} MiB", flush=True)
        time.sleep(2)
        # 预热
        chat([{"role": "user", "content": "hi"}], n_predict=16, effort="low")
        if "a" in phases:
            result["phase_a"] = phase_a()
        if "t" in phases:
            result["phase_t"] = phase_t()
        if "b" in phases:
            result["phase_b"] = phase_b()
        if "c" in phases:
            result["phase_c"] = phase_c()
        if "d" in phases:
            result["phase_d"] = phase_d()
    finally:
        kill()
        log.close()
    # 已有结果保留：分阶段跑时不要互相覆盖
    rp = ROOT / "wf_result.json"
    merged = {}
    if rp.exists():
        try:
            merged = json.loads(rp.read_text(encoding="utf-8"))
        except Exception:
            merged = {}
    merged.update(result)
    rp.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n结果已写入 wf_result.json", flush=True)


if __name__ == "__main__":
    main()
