# -*- coding: utf-8 -*-
"""
Prefix-cache / KV-reuse probe for Bonsai 2 27B on 8GB.

QUESTION
    WorkBuddy 每轮发来的 prompt 结构是：
        [系统提示 + 工具定义 + 技能清单]  (几乎逐字节相同, ~50k token)
        [对话历史]
    实测 55,273 token 的请求 prefill 跑了 458 秒 → 客户端先超时断开。
    如果前缀能被复用，第二轮起就不该再跑 prefill。

    但系统提示里含 <current_time> 之类每轮变化的字段 —— 变化虽小，
    却会让"严格前缀匹配"在开头就断掉，导致整段重算。

    llama-server 有 --cache-reuse N（默认 0=关），专治这种
    "中间一小段变了、后面全一样" 的情况（靠 KV shifting）。

WHAT IT MEASURES
    三个请求，正文 BIG 完全相同（约 6k token）：
      P1 = HEAD_A + BIG + 问题     首次，必然全量 prefill
      P2 = HEAD_B + BIG + 问题     HEAD 变了十几个 token（模拟时间戳变化）
      P3 = HEAD_B + BIG + 问题     P2 的逐字节重复（严格前缀，理论 0 prefill）

    对比 cache-reuse = 0 / 256 / 1024 三档下 P2 的 prefill 开销。

SAFETY
    显存闸门：加载后 >= 7960 MiB 立即中止（04:52 蓝屏就是因为越线后
    驱动悄悄把缓冲搬到系统内存，速度塌成 1/10，再叠加满载跑崩了虚拟化层）。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BIN    = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo\bin\llama-server.exe"
MODEL  = r"D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
FILLER = r"D:\Bonsai-demo\surgery\docs\QUALITY.md"
LOG    = r"D:\Bonsai-demo\_reuse_server.log"
PORT   = 8082
BIG_TOKENS = 6000

CONFIGS = [
    ("cache-reuse 0    (当前生产配置)", "0"),
    ("cache-reuse 256",                  "256"),
    ("cache-reuse 1024",                 "1024"),
]

VRAM_LIMIT = 7960

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(path, obj, timeout=1800):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (PORT, path),
        data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with _opener.open(req, timeout=timeout) as r:
        return json.load(r)


def get(path, timeout=30):
    with _opener.open("http://127.0.0.1:%d%s" % (PORT, path), timeout=timeout) as r:
        return json.load(r)


def vram_mib():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20)
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return -1


def wait_health(deadline=360):
    t0 = time.time()
    while time.time() - t0 < deadline:
        try:
            if get("/health", timeout=5).get("status") == "ok":
                return time.time() - t0
        except Exception:
            pass
        time.sleep(2)
    return None


def kill_server():
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                   capture_output=True, text=True)
    time.sleep(4)


def ntok(text):
    r = post("/tokenize", {"content": text})
    t = r.get("tokens")
    return len(t) if isinstance(t, list) else int(t)


def build_big(target):
    raw = open(FILLER, encoding="utf-8", errors="ignore").read()
    unit = raw + "\n\n"
    n_unit = max(1, ntok(unit))
    text = unit * max(1, int(target / n_unit))
    for _ in range(8):
        n = ntok(text)
        if abs(n - target) < 200:
            break
        if n < target:
            text += unit * max(1, int((target - n) / n_unit))
        else:
            text = text[: max(2000, int(len(text) * target / max(n, 1)))]
    return text, ntok(text)


def ask(prompt_text, tag):
    """Send one chat request, return timings."""
    t0 = time.time()
    resp = post("/v1/chat/completions", {
        "model": "bench",
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 16,
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    }, timeout=1800)
    wall = time.time() - t0
    tm = resp.get("timings") or {}
    pp_ms = tm.get("prompt_ms", 0) or 0
    n_pp = tm.get("prompt_n", 0) or 0
    print("    %-6s prompt_tokens=%-6s prefill=%7.2f s (%8.1f t/s)  墙钟=%6.2f s"
          % (tag, n_pp, pp_ms / 1000.0, tm.get("prompt_per_second", 0) or 0, wall))
    return {"tag": tag, "pp_ms": pp_ms, "n_pp": n_pp,
            "pp_s": tm.get("prompt_per_second", 0) or 0, "wall": wall}


def run_one(label, reuse):
    print("\n" + "=" * 78)
    print("配置: %s    --cache-reuse %s" % (label, reuse))
    print("=" * 78)
    if os.path.exists(LOG):
        os.remove(LOG)
    args = [
        BIN, "-m", MODEL, "-ngl", "99", "-fa", "on", "-np", "1", "-c", "65536",
        "-b", "2048", "-ub", "512", "-ctk", "q4_0", "-ctv", "q4_0",
        "--cache-reuse", str(reuse),
        "--backend-sampling", "--jinja",
        "--host", "127.0.0.1", "--port", str(PORT), "--alias", "bench",
        "-lv", "2",
    ]
    logf = open(LOG, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    try:
        load_s = wait_health(360)
        if load_s is None:
            print("!! 启动失败")
            print(open(LOG, encoding="utf-8", errors="ignore").read()[-1200:])
            return None
        u = vram_mib()
        print("加载就绪 %.1f s   显存 %d MiB" % (load_s, u))
        if u >= VRAM_LIMIT:
            print("!! 显存越线 >= %d MiB，中止该配置（不重演蓝屏）" % VRAM_LIMIT)
            return None

        big, n_big = build_big(BIG_TOKENS)
        print("正文 BIG 实测 %d token" % n_big)

        # HEAD 只差时间戳 —— 模拟 WorkBuddy 注入的 current_time
        head_a = "【环境】当前时间：2026年9月27日 05:00:00（星期日）。"
        head_b = "【环境】当前时间：2026年9月27日 05:07:31（星期日）。"
        tail = "\n\n请用一句话概括上面文档的核心内容。"

        print("  -- 三连请求 --")
        r1 = ask(head_a + big + tail, "P1")
        r2 = ask(head_b + big + tail, "P2")
        r3 = ask(head_b + big + tail, "P3")
        peak = vram_mib()
        print("  显存峰值 %d MiB" % peak)

        out = {"label": label, "reuse": reuse, "load_s": load_s,
               "n_big": n_big, "vram_peak": peak, "P1": r1, "P2": r2, "P3": r3}
        if r1["pp_ms"] > 0:
            out["p2_ratio"] = r2["pp_ms"] / r1["pp_ms"]
            print("  >> P2/P1 prefill 比 = %.3f  (%.0f%% 被省掉)"
                  % (out["p2_ratio"], (1 - out["p2_ratio"]) * 100))
        return out
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        logf.close()
        kill_server()


def main():
    rows = []
    for label, reuse in CONFIGS:
        try:
            r = run_one(label, reuse)
            if r:
                rows.append(r)
        except Exception as e:
            print("!! %s 异常: %r" % (label, e))
            kill_server()
    print("\n" + "=" * 78)
    print("汇总（BIG ≈ %d token；P2 = 开头十来个 token 变了）" % BIG_TOKENS)
    print("%-32s %10s %10s %10s %8s" % ("配置", "P1 s", "P2 s", "P3 s", "P2/P1"))
    for r in rows:
        print("%-32s %10.2f %10.2f %10.2f %8.3f"
              % (r["label"], r["P1"]["pp_ms"] / 1000.0, r["P2"]["pp_ms"] / 1000.0,
                 r["P3"]["pp_ms"] / 1000.0, r.get("p2_ratio", -1)))
    json.dump(rows, open(r"D:\Bonsai-demo\_reuse_probe.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    kill_server()


if __name__ == "__main__":
    main()
