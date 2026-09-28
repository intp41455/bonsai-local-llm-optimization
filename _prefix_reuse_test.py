# -*- coding: utf-8 -*-
"""
Prefix-reuse test.

WorkBuddy sends the SAME ~50k-token prefix (system prompt + tool defs + skill list)
on every turn. If llama-server reuses the KV of that prefix, only the first turn
pays the full prefill cost. This script proves or disproves it.

  turn 1 : 48k filler + question            -> expect full prefill
  turn 2 : same 48k + tiny delta            -> expect near-zero prefill if reuse works
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BIN = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo\bin\llama-server.exe"
MODEL = r"D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
FILLER = r"D:\Bonsai-demo\surgery\docs\QUALITY.md"
PORT = 8081
TARGET = 48000

_op = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post(path, obj, timeout=1800):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path),
                                 data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with _op.open(req, timeout=timeout) as r:
        return json.load(r)


def get(path, timeout=10):
    with _op.open("http://127.0.0.1:%d%s" % (PORT, path), timeout=timeout) as r:
        return json.load(r)


def ntok(t):
    r = post("/tokenize", {"content": t}).get("tokens")
    return len(r) if isinstance(r, list) else int(r)


def vram():
    o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True, timeout=20)
    return int(o.stdout.strip().splitlines()[0])


def kill():
    subprocess.run(["cmd", "/c", "taskkill", "/F", "/IM", "llama-server.exe"],
                   capture_output=True, text=True)
    time.sleep(4)


def build(target):
    raw = open(FILLER, encoding="utf-8", errors="ignore").read()
    unit = raw + "\n\n"
    n1 = ntok(unit)
    text = unit * max(1, int(target / n1))
    for _ in range(8):
        n = ntok(text)
        if abs(n - target) < 300:
            break
        d = target - n
        text = (text + unit * max(1, int(d / n1))) if d > 0 else text[: max(2000, int(len(text) * target / n))]
    return text


def ask(msgs, label):
    t0 = time.time()
    r = post("/v1/chat/completions", {
        "model": "bench", "messages": msgs, "max_tokens": 24, "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    })
    wall = time.time() - t0
    tm = r.get("timings") or {}
    print("  %-22s prefill %7.1f s (%6.1f t/s) | decode %5.2f t/s | 端到端 %6.1f s"
          % (label, (tm.get("prompt_ms", 0) or 0) / 1000.0,
             tm.get("prompt_per_second", 0) or 0,
             tm.get("predicted_per_second", 0) or 0, wall))
    return tm


def main():
    kill()
    args = [BIN, "-m", MODEL, "-ngl", "99", "-fa", "on", "-np", "1", "-c", "65536",
            "-b", "2048", "-ub", "512", "-ctk", "q4_0", "-ctv", "q4_0",
            "--backend-sampling", "--jinja",
            "--host", "127.0.0.1", "--port", str(PORT), "--alias", "bench"]
    lg = open(r"D:\Bonsai-demo\_reuse_server.log", "w", encoding="utf-8", errors="ignore")
    p = subprocess.Popen(args, stdout=lg, stderr=subprocess.STDOUT)
    try:
        t0 = time.time()
        while time.time() - t0 < 300:
            try:
                if get("/health").get("status") == "ok":
                    break
            except Exception:
                time.sleep(2)
        print("服务就绪，显存 %d MiB" % vram())

        base = build(TARGET)
        q = "\n\n请用一句话总结上面这段文档的核心内容。"
        print("base prompt = %d token" % ntok(base + q))

        print("\n--- turn 1（全新会话，必须从头 prefill）---")
        ask([{"role": "user", "content": base + q}], "turn1")

        print("\n--- turn 2（同一前缀 + 40 字增量）---")
        ask([{"role": "user", "content": base + q},
             {"role": "assistant", "content": "已收到。"},
             {"role": "user", "content": "再补一句：这段文档的结论是什么？"}], "turn2")

        print("\n--- turn 3（同一前缀 + 再增量）---")
        ask([{"role": "user", "content": base + q},
             {"role": "assistant", "content": "已收到。"},
             {"role": "user", "content": "再补一句：这段文档的结论是什么？"},
             {"role": "assistant", "content": "见上。"},
             {"role": "user", "content": "把结论压缩成 10 个字。"}], "turn3")
    finally:
        try:
            p.terminate()
        except Exception:
            pass
        lg.close()
        kill()


if __name__ == "__main__":
    main()
