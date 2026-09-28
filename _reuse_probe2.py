# -*- coding: utf-8 -*-
"""
Decisive test: does WorkBuddy's SECOND turn reuse the KV cache?

上一步已证明：llama-server 对"逐字节相同的 prompt"能 100% 复用（只评估 4 个 token）。
所以 458 秒 prefill 只可能来自两种情况之一：
    A) 每次请求都是冷启动（客户端取消 → 槽位重置 → 重试再冷启动）
    B) 系统提示开头每轮都变（时间戳等），导致严格前缀匹配在几千 token 处断掉

本脚本用 12k token 的"准系统提示"SYS 复现两种工况：

    E0  严格追加（正确情况）
        R1 = SYS + Q1
        R2 = SYS + Q1 + A1 + Q2          <- SYS 逐字节相同，只是后面追加
        预期 R2 评估 token 数 ≈ 0（近乎免费）

    E1  开头变了（最坏情况）
        R1 = headA + SYS + Q1
        R2 = headB + SYS + Q1 + A1 + Q2  <- 开头十来个 token 不同
        预期 R2 全量重算 ≈ 12k

    E2  SYS 中间插了一段变量（模拟记忆/技能清单变化）
        R1 = SYS_前半 + midA + SYS_后半 + Q1
        R2 = SYS_前半 + midB + SYS_后半 + Q1 + A1 + Q2
        预期 R2 从 mid 处重算后半段

    对 E0/E1/E2 都测 cache-reuse 0 与 1024 两档。

判据：看 resp.timings.prompt_n（实际被评估的 token 数），不是墙钟。
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
LOG    = r"D:\Bonsai-demo\_reuse2_server.log"
PORT   = 8084
VRAM_LIMIT = 7960
SYS_TOKENS = 12000

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(path, obj, timeout=1800):
    req = urllib.request.Request(
        "http://127.0.0.1:%d%s" % (PORT, path),
        data=json.dumps(obj).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with _opener.open(req, timeout=timeout) as r:
        return json.load(r)


def get(path, timeout=30):
    with _opener.open("http://127.0.0.1:%d%s" % (PORT, path), timeout=timeout) as r:
        return json.load(r)


def vram():
    try:
        o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                            "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=20)
        return int(o.stdout.strip().splitlines()[0])
    except Exception:
        return -1


def wait_health(deadline=420):
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


def ntok(t):
    r = post("/tokenize", {"content": t})
    tk = r.get("tokens")
    return len(tk) if isinstance(tk, list) else int(tk)


def build_filler(target):
    raw = open(FILLER, encoding="utf-8", errors="ignore").read()
    unit = raw + "\n\n"
    n1 = max(1, ntok(unit))
    text = unit * max(1, int(target / n1))
    n = ntok(text)
    if n > target:
        text = text[: max(500, int(len(text) * target / n))]
    return text, ntok(text)


def send(messages, tag):
    t0 = time.time()
    resp = post("/v1/chat/completions", {
        "model": "bench", "messages": messages,
        "max_tokens": 12, "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    }, timeout=1800)
    wall = time.time() - t0
    tm = resp.get("timings") or {}
    n = tm.get("prompt_n", 0) or 0
    ms = tm.get("prompt_ms", 0) or 0
    print("      %-4s 评估 %6d token  prefill %7.2f s  墙钟 %6.2f s"
          % (tag, n, ms / 1000.0, wall))
    return {"tag": tag, "n_eval": n, "pp_ms": ms, "wall": wall}


def scenario(label, sys_text, reuse):
    """跑 E0/E1/E2 三工况中的一个，返回 R2 的评估 token 数。"""
    print("\n" + "-" * 78)
    print("工况 %s   (cache-reuse %s)" % (label, reuse))
    print("-" * 78)

    def msgs(*parts, **kw):
        if kw.get("sys"):
            return [{"role": "system", "content": kw["sys"]}] + list(parts)
        return list(parts)

    Q1 = "问题一：用一句话说明什么是 KV cache 前缀复用。"
    A1 = "回答一：前缀复用指服务端保留已计算的 KV，下一轮只需计算新增 token。"
    Q2 = "问题二：那么第二轮大概能省多少计算量？"

    r1 = send(msgs({"role": "user", "content": Q1}, sys=sys_text["r1"]), "R1")
    r2 = send(msgs({"role": "user", "content": Q1},
                   {"role": "assistant", "content": A1},
                   {"role": "user", "content": Q2}, sys=sys_text["r2"]), "R2")
    ratio = (r2["n_eval"] / r1["n_eval"]) if r1["n_eval"] else -1
    print("      >> R2/R1 评估量比 = %.3f   (省 %d%%)"
          % (ratio, max(0, int((1 - ratio) * 100))))
    return {"label": label, "reuse": reuse, "R1": r1, "R2": r2, "ratio": ratio}


def build_scenarios(sys_body):
    """返回 E0/E1/E2 三个工况的 sys_text 字典（构造 R1/R2 的系统提示）。"""
    headA = "【环境】当前时间：2026年9月27日 05:00:00。"
    headB = "【环境】当前时间：2026年9月27日 05:07:31。"   # 只差时间
    midA = "\n\n【记忆】本轮检索到 0 条历史记录。\n\n"
    midB = "\n\n【记忆】本轮检索到 3 条历史记录，涉及 Bonsai 部署、显存调优、锁频事故。\n\n"
    half = len(sys_body) // 2

    return {
        "E0 严格追加（SYS 完全相同）": {
            "r1": sys_body, "r2": sys_body,
        },
        "E1 开头变了（时间戳）": {
            "r1": headA + sys_body, "r2": headB + sys_body,
        },
        "E2 中间插了变量（记忆块）": {
            "r1": sys_body[:half] + midA + sys_body[half:],
            "r2": sys_body[:half] + midB + sys_body[half:],
        },
    }


def main():
    rows = []
    for reuse in ("0", "1024"):
        print("\n" + "=" * 78)
        print("=== cache-reuse %s ===" % reuse)
        print("=" * 78)
        if os.path.exists(LOG):
            os.remove(LOG)
        args = [BIN, "-m", MODEL, "-ngl", "99", "-fa", "on", "-np", "1",
                "-c", "65536", "-b", "2048", "-ub", "512",
                "-ctk", "q4_0", "-ctv", "q4_0",
                "--cache-reuse", reuse,
                "--backend-sampling", "--jinja",
                "--host", "127.0.0.1", "--port", str(PORT), "--alias", "bench",
                "-lv", "2"]
        logf = open(LOG, "w", encoding="utf-8", errors="ignore")
        proc = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
        try:
            load_s = wait_health(420)
            if load_s is None:
                print("!! 启动失败")
                print(open(LOG, encoding="utf-8", errors="ignore").read()[-1000:])
                continue
            u = vram()
            print("加载就绪 %.1f s  显存 %d MiB" % (load_s, u))
            if u >= VRAM_LIMIT:
                print("!! 显存越线，跳过")
                continue

            body, n_body = build_filler(SYS_TOKENS)
            print("SYS 实测 %d token" % n_body)

            for label, st in build_scenarios(body).items():
                try:
                    rows.append(scenario(label, st, reuse))
                except Exception as e:
                    print("   !! %s 异常 %r" % (label, e))
        finally:
            try:
                proc.terminate()
            except Exception:
                pass
            logf.close()
            kill_server()

    print("\n" + "=" * 78)
    print("汇总：R2 实际被评估的 token 数 / R1 (SYS ≈ %d token)" % SYS_TOKENS)
    print("%-34s %8s %10s %10s %9s" % ("工况", "reuse", "R1 评估", "R2 评估", "R2/R1"))
    for r in rows:
        print("%-34s %8s %10d %10d %9.3f"
              % (r["label"], r["reuse"], r["R1"]["n_eval"], r["R2"]["n_eval"], r["ratio"]))
    json.dump(rows, open(r"D:\Bonsai-demo\_reuse2.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    kill_server()


if __name__ == "__main__":
    main()
