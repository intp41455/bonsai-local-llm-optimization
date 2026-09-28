# -*- coding: utf-8 -*-
"""
Ubatch x prefill-throughput test（上轮被蓝屏打断的实验，重做版）。

WHY
    实测 prefill 吞吐随深度从 ~512 t/s 掉到 ~120 t/s：
        55,273 token 的 Agent 请求  ->  prefill 458 秒
    prefill 吞吐主要受 ubatch 大小支配（注意力矩阵是 ubatch x n_kv）。
    上轮试 -ub 2048 直接显存越线 -> 蓝屏，已永久废弃。

    本轮在**更小的上下文** c49152 上试 1024 / 1536，
    每一步都过显存闸门，并为每次推理挂监督线程（越线 2 次即杀）。

MATRIX
    c49152 / ub512   基线
    c49152 / ub1024
    c49152 / ub1536  （只有上一档显存余量 >= 300 MiB 才跑）

METRIC
    真正要看的是 timing.prompt_per_second 与峰值显存。
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BIN    = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo\bin\llama-server.exe"
MODEL  = r"D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
FILLER = r"D:\Bonsai-demo\surgery\docs\QUALITY.md"
LOG    = r"D:\Bonsai-demo\_ub_server.log"
PORT   = 8085
CTX    = "49152"
VRAM_LIMIT = 7900
PROMPT_TOKENS = 20000

MATRIX = [("ub512", "512"), ("ub1024", "1024"), ("ub1536", "1536")]

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


def run_one(label, ub):
    print("\n" + "=" * 78)
    print("配置 c%s / %s / MTP off" % (CTX, label))
    print("=" * 78)
    if os.path.exists(LOG):
        os.remove(LOG)
    args = [BIN, "-m", MODEL, "-ngl", "99", "-fa", "on", "-np", "1",
            "-c", CTX, "-b", "2048", "-ub", ub,
            "-ctk", "q4_0", "-ctv", "q4_0",
            "--backend-sampling", "--jinja",
            "--host", "127.0.0.1", "--port", str(PORT), "--alias", "bench",
            "-lv", "2"]
    logf = open(LOG, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    try:
        load_s = wait_health(420)
        if load_s is None:
            print("!! 加载失败")
            print(open(LOG, encoding="utf-8", errors="ignore").read()[-1000:])
            return None
        u0 = vram()
        print("加载就绪 %.1f s   显存 %d MiB (%s)" % (load_s, u0, ub))
        if u0 >= VRAM_LIMIT:
            print("!! 加载即越线，跳过")
            return None

        body, n_body = build_filler(PROMPT_TOKENS)
        print("prompt 实测 %d token" % n_body)

        stop = {"v": False, "n": 0, "hit": 0}

        def watchdog():
            while not stop["v"]:
                time.sleep(3)
                stop["n"] += 1
                uu = vram()
                if uu >= VRAM_LIMIT:
                    stop["hit"] += 1
                    print("   [!] 监督: 显存 %d MiB 超线 (%d/2)" % (uu, stop["hit"]))
                    if stop["hit"] >= 2:
                        print("   [!] 监督: 判定越线兜底 -> 立即终止服务")
                        kill_server()
                        return
        th = threading.Thread(target=watchdog, daemon=True)
        th.start()

        peak = [u0]

        def sampler():
            while not stop["v"]:
                v = vram()
                if v > peak[0]:
                    peak[0] = v
                time.sleep(1)
        threading.Thread(target=sampler, daemon=True).start()

        t0 = time.time()
        try:
            resp = post("/v1/chat/completions", {
                "model": "bench",
                "messages": [{"role": "user",
                              "content": body + "\n\n请用一句话概括上文核心。"}],
                "max_tokens": 24, "temperature": 0.0,
                "chat_template_kwargs": {"enable_thinking": False},
            }, timeout=1500)
        except Exception as e:
            print("!! 推理异常（可能被监督终止）: %r" % e)
            return None
        finally:
            stop["v"] = True

        wall = time.time() - t0
        tm = resp.get("timings") or {}
        pp = tm.get("prompt_per_second", 0) or 0
        pp_n = tm.get("prompt_n", 0) or 0
        print("-" * 78)
        print("prefill : %.1f t/s  (%d token, %.1f s)" % (pp, pp_n, pp_n / max(pp, 1)))
        print("decode  : %.2f t/s" % (tm.get("predicted_per_second", 0) or 0))
        print("墙钟    : %.1f s   显存峰值 %d MiB" % (wall, peak[0]))
        ok = pp > 60
        if not ok:
            print("  >> 判定: 不可用（prefill 吞吐 %.1f t/s 异常）" % pp)
        return {"label": label, "ub": ub, "ok": ok, "pp": pp, "pp_n": pp_n,
                "tg": tm.get("predicted_per_second", 0) or 0, "wall": wall,
                "vram_peak": peak[0], "vram_load": u0, "load_s": load_s}
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        logf.close()
        kill_server()


def main():
    rows = []
    for label, ub in MATRIX:
        try:
            r = run_one(label, ub)
            if r:
                rows.append(r)
            if r and r["vram_peak"] < VRAM_LIMIT - 350:
                print("   (显存余量充足，继续下一档)")
            elif r:
                print("   (显存余量不足 350 MiB，停止继续加档)")
                break
        except Exception as e:
            print("!! %s 异常: %r" % (label, e))
            kill_server()

    print("\n" + "=" * 78)
    print("ubatch x prefill 汇总（c%s, prompt ≈ %d token）" % (CTX, PROMPT_TOKENS))
    print("%-10s %12s %12s %10s %10s" % ("配置", "prefill t/s", "decode t/s", "显存峰值", "墙钟 s"))
    for r in rows:
        print("%-10s %12.1f %12.2f %10d %10.1f"
              % (r["label"], r["pp"], r["tg"], r["vram_peak"], r["wall"]))
    json.dump(rows, open(r"D:\Bonsai-demo\_ub_test.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    kill_server()


if __name__ == "__main__":
    main()
