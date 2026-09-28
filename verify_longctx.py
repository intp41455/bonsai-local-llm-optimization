# -*- coding: utf-8 -*-
"""
长上下文验证：复现 WorkBuddy 报错场景（prompt 48937 token > 旧窗口 32768），
确认 65536 窗口能装下。用 /tokenize 精确校准 token 数，不靠字符估算。
"""
import sys, json, time, urllib.request, urllib.error

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8080"
SOURCES = [
    r"D:\Bonsai-demo\surgery\docs\QUALITY.md",
    r"D:\Bonsai-demo\提示词模板与调参手册.md",
    r"D:\Bonsai-demo\Bonsai2-27B-8GB部署交付报告.md",
]
TARGET_TOKENS = 49000          # 报错值 48937，取其上方一点


def post(path, body, timeout=900):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8")), time.time() - t0
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw), time.time() - t0
        except Exception:
            return e.code, {"raw": raw[:500]}, time.time() - t0
    except Exception as e:
        return -1, {"err": str(e)}, time.time() - t0


def load_src():
    s = ""
    for p in SOURCES:
        try:
            s += open(p, encoding="utf-8", errors="ignore").read() + "\n\n"
        except Exception:
            pass
    if len(s) < 5000:
        s = ("机器学习模型的量化是指将高精度权重映射到低位宽表示的过程，"
             "在保持精度的同时显著降低存储与计算开销。\n") * 200
    return s


def token_count(text):
    st, d, _ = post("/tokenize", {"content": text}, timeout=300)
    if st == 200:
        return len(d.get("tokens", []))
    return None


def main():
    print("=" * 70)
    print("  长上下文验证 — 目标 %d token（WorkBuddy 报错值 48937）" % TARGET_TOKENS)
    print("=" * 70)

    try:
        with urllib.request.urlopen(BASE + "/health", timeout=10) as r:
            print("[1] 服务健康:", r.read().decode()[:40])
    except Exception as e:
        print("[1] 服务不可达:", e)
        sys.exit(1)

    # 窗口确认
    try:
        with urllib.request.urlopen(BASE + "/v1/models", timeout=15) as r:
            m = json.loads(r.read().decode())["data"][0]["meta"]
        print("[2] 服务端窗口 n_ctx = %s" % m["n_ctx"])
    except Exception:
        pass

    src = load_src()
    print("[3] 素材 %d 字符，开始校准 token 数..." % len(src))

    # 线性校准：先全量 tokenize，按比例截断，再复核
    text = src
    for i in range(3):
        n = token_count(text)
        if n is None:
            print("    /tokenize 不可用，回退字符估算")
            break
        print("    第%d次: %d 字符 = %d token" % (i + 1, len(text), n))
        if abs(n - TARGET_TOKENS) / TARGET_TOKENS < 0.01:
            break
        ratio = TARGET_TOKENS / n
        need = int(len(text) * ratio)
        if need <= len(text):
            text = text[:max(1000, need)]
        else:                      # 素材不够长 -> 重复拼接扩展（只验证 prompt 被接受，不求输出质量）
            base = text
            while len(text) < need:
                text += base
            text = text[:need]

    final_n = token_count(text)
    print("[4] 最终 prompt: %d 字符 ≈ %s token" % (len(text), final_n))

    body = {
        "model": "bonsai-2-27b",
        "messages": [{"role": "user",
                      "content": text + "\n\n以上材料一共提到过几次「量化」？只回答一个数字。"}],
        "max_tokens": 16,
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    print("[5] 发送请求（prefill 约需 1-2 分钟）...")
    st, d, dt = post("/v1/chat/completions", body)

    print()
    print("=" * 70)
    if st == 200:
        u = d.get("usage", {}) or {}
        t = d.get("timings", {}) or {}
        print("  ✅ HTTP 200 —— prompt 被接受，窗口足够")
        print("     prompt_tokens : %s" % u.get("prompt_tokens"))
        print("     prefill       : %.2f t/s" % t.get("prompt_per_second", 0))
        print("     decode        : %.2f t/s" % t.get("predicted_per_second", 0))
        print("     总耗时        : %.1f s" % dt)
        print("     回复          : %s" % (d["choices"][0]["message"]["content"] or "")[:100])
    else:
        print("  ❌ HTTP %s —— 仍然失败" % st)
        print("  %s" % json.dumps(d, ensure_ascii=False)[:600])
    print("=" * 70)


if __name__ == "__main__":
    main()
