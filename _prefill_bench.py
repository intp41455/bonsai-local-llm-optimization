# -*- coding: utf-8 -*-
"""
Prefill benchmark for Bonsai 2 27B on 8GB.
Compares -ub / -b settings at a realistic long-context prompt (~48k tokens),
which is what a WorkBuddy agent request looks like.

Usage:  python _prefill_bench.py
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
LOG = r"D:\Bonsai-demo\_bench_server.log"
PORT = 8081
TARGET_TOKENS = 48000

# (label, batch, ubatch)
CONFIGS = [
    ("ub512_b2048  (当前配置)", "2048", "512"),
    ("ub2048_b4096 (候选)",     "4096", "2048"),
]

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
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20,
        )
        used, total = out.stdout.strip().splitlines()[0].split(",")
        return int(used.strip())
    except Exception:
        return -1


VRAM_LIMIT = 7960   # 超过即认为已进入 WDDM 系统内存兜底（=性能崩塌）


def vram_guard(tag):
    """模型加载后立刻检查显存水位；越线就立即中止，绝不再跑长 prefill。"""
    u = vram_mib()
    print("  [显存闸门] %s: %d MiB / 8151 MiB" % (tag, u))
    if u >= VRAM_LIMIT:
        print("  !! 显存水位越线（>= %d MiB），判定为会触发系统内存兜底，" % VRAM_LIMIT)
        print("  !! 立即中止该配置，避免重演 04:52 的蓝屏。")
        return False
    return True


def wait_health(deadline=360):
    t0 = time.time()
    while time.time() - t0 < deadline:
        try:
            d = get("/health", timeout=5)
            if d.get("status") == "ok":
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
    """Real token count via the server's own tokenizer."""
    r = post("/tokenize", {"content": text})
    t = r.get("tokens")
    return len(t) if isinstance(t, list) else int(t)


def build_text(target):
    """Expand the filler doc until /tokenize reports ~target tokens."""
    raw = open(FILLER, encoding="utf-8", errors="ignore").read()
    if len(raw) < 2000:
        raw = (raw + "\n") * (3000 // max(len(raw), 1) + 1)
    unit = raw + "\n\n"
    n_unit = ntok(unit)
    reps = max(1, int(target / n_unit))
    text = unit * reps
    for _ in range(8):
        n = ntok(text)
        if abs(n - target) < 300:
            break
        delta = target - n
        if delta > 0:
            text += unit * max(1, int(delta / n_unit))
        else:
            keep = int(len(text) * target / max(n, 1))
            text = text[: max(2000, keep)]
    return text, ntok(text)


def run_one(label, b, ub):
    print("\n" + "=" * 74)
    print("配置: %s   -b %s -ub %s" % (label, b, ub))
    print("=" * 74)
    if os.path.exists(LOG):
        os.remove(LOG)
    args = [
        BIN, "-m", MODEL, "-ngl", "99", "-fa", "on", "-np", "1", "-c", "65536",
        "-b", b, "-ub", ub, "-ctk", "q4_0", "-ctv", "q4_0",
        "--backend-sampling", "--jinja",
        "--host", "127.0.0.1", "--port", str(PORT), "--alias", "bench",
        "-lv", "3",
    ]
    logf = open(LOG, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    try:
        load_s = wait_health(360)
        if load_s is None:
            print("!! 启动失败（360s 内未就绪）—— 该配置不可用")
            tail = open(LOG, encoding="utf-8", errors="ignore").read()[-1500:]
            print(tail)
            return None
        print("模型加载就绪: %.1f s   显存: %d MiB" % (load_s, vram_mib()))

        text, ntok = build_text(TARGET_TOKENS)
        print("prompt 实测 token: %d" % ntok)

        t0 = time.time()
        resp = post("/v1/chat/completions", {
            "model": "bench",
            "messages": [{"role": "user",
                          "content": text + "\n\n请用一句话总结上面这段文档的核心内容。"}],
            "max_tokens": 32,
            "temperature": 0.0,
            "chat_template_kwargs": {"enable_thinking": False},
        }, timeout=1800)
        wall = time.time() - t0
        tm = resp.get("timings") or {}
        pp_s = tm.get("prompt_per_second", 0) or 0
        tg_s = tm.get("predicted_per_second", 0) or 0
        pp_ms = tm.get("prompt_ms", 0) or 0
        print("-" * 74)
        print("prefill : %.1f s  (%.1f t/s)" % (pp_ms / 1000.0, pp_s))
        print("decode  : %.2f t/s" % tg_s)
        print("端到端  : %.1f s" % wall)
        print("显存峰值: %d MiB" % vram_mib())
        print("回复    : %s" % (resp["choices"][0]["message"]["content"] or "")[:120].replace("\n", " "))
        return {"label": label, "pp_s": pp_s, "pp_s_wall": pp_ms / 1000.0,
                "tg_s": tg_s, "wall": wall, "ntok": ntok, "load_s": load_s,
                "vram": vram_mib()}
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        logf.close()
        kill_server()


def main():
    results = []
    for label, b, ub in CONFIGS:
        try:
            r = run_one(label, b, ub)
            if r:
                results.append(r)
        except Exception as e:
            print("!! %s 异常: %r" % (label, e))
            kill_server()
    print("\n" + "=" * 74)
    print("汇总（prompt ≈ %d token）" % TARGET_TOKENS)
    print("%-26s %10s %10s %8s %9s" % ("配置", "prefill s", "prefill t/s", "decode", "显存 MiB"))
    for r in results:
        print("%-26s %10.1f %10.1f %8.2f %9d"
              % (r["label"], r["pp_s_wall"], r["pp_s"], r["tg_s"], r["vram"]))
    json.dump(results, open(r"D:\Bonsai-demo\_prefill_bench.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    kill_server()


if __name__ == "__main__":
    main()
