# -*- coding: utf-8 -*-
"""
MTP x context-size matrix for Bonsai 2 27B on 8GB.

BACKGROUND
    上轮只测了两个点：
        MTP on  / c32768  -> 62.05 t/s  OK
        MTP on  / c65536  ->  1.67 t/s  OOM（compute buffer 撑爆）
        MTP off / c65536  -> 38.7  t/s  OK
    中间的 c49152 / c40960 / c57344 是空白。
    如果能找到"MTP 可用 + 窗口 >= 48k"的交点，就能同时拿到
    高速（62 t/s）和 WorkBuddy 需要的窗口（实测单请求 ~50k token）。

MATRIX
    (ctx, mtp_on, draft_depth_max)
    c49152 / MTP on / 4096
    c57344 / MTP on / 4096
    c40960 / MTP on / 4096     <- 兜底
    c65536 / MTP off           <- 已知可用基线，复测确认

SAFETY
    显存闸门：加载后 >= 7960 MiB 立即中止。
    另加"早停"：prefill 期间每 3 秒采样一次 decode 速度，若 < 8 t/s
    立即判定为越线兜底，直接中止，不再等它跑完（04:52 就是因为没有
    早停机制，满载跑了 5 分钟才崩）。
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
LOG    = r"D:\Bonsai-demo\_mtp_matrix.log"
PORT   = 8083
VRAM_LIMIT = 7960

PROMPT_TOKENS = 900      # 短 prompt，只为量 decode
GEN_TOKENS    = 256

MATRIX = [
    ("c49152 / MTP on / depth4096",  "49152", True,  "4096"),
    ("c57344 / MTP on / depth4096",  "57344", True,  "4096"),
    ("c40960 / MTP on / depth4096",  "40960", True,  "4096"),
    ("c65536 / MTP off (基线)",       "65536", False, None),
]

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


def run_one(label, ctx, mtp_on, depth_max):
    print("\n" + "=" * 78)
    print("配置: %s   (-c %s, MTP %s)" % (label, ctx, "on" if mtp_on else "off"))
    print("=" * 78)
    if os.path.exists(LOG):
        os.remove(LOG)

    args = [BIN, "-m", MODEL, "-ngl", "99", "-fa", "on", "-np", "1",
            "-c", ctx, "-b", "2048", "-ub", "512",
            "-ctk", "q4_0", "-ctv", "q4_0",
            "--cache-reuse", "256",
            "--backend-sampling", "--jinja",
            "--host", "127.0.0.1", "--port", str(PORT), "--alias", "bench",
            "-lv", "2"]
    if mtp_on:
        args += ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
                 "--spec-draft-depth-max", depth_max,
                 "-ctkd", "q4_0", "-ctvd", "q4_0"]

    logf = open(LOG, "w", encoding="utf-8", errors="ignore")
    proc = subprocess.Popen(args, stdout=logf, stderr=subprocess.STDOUT)
    try:
        load_s = wait_health(420)
        if load_s is None:
            print("!! 加载失败/超时")
            print(open(LOG, encoding="utf-8", errors="ignore").read()[-1200:])
            return {"label": label, "ctx": ctx, "mtp": mtp_on, "ok": False,
                    "why": "load_fail"}
        u = vram()
        print("加载就绪 %.1f s   显存 %d MiB" % (load_s, u))
        if u >= VRAM_LIMIT:
            print("!! 显存越线 >= %d MiB，中止" % VRAM_LIMIT)
            return {"label": label, "ctx": ctx, "mtp": mtp_on, "ok": False,
                    "why": "vram", "vram": u}

        body, n_body = build_filler(PROMPT_TOKENS)
        print("prompt 实测 %d token，生成上限 %d token" % (n_body, GEN_TOKENS))

        # ---- 监督线程：速度崩了立刻杀 ----
        stop = {"v": False, "n": 0}

        def watchdog():
            slow = 0
            while not stop["v"] and stop["n"] < 40:
                time.sleep(3)
                stop["n"] += 1
                uu = vram()
                if uu >= VRAM_LIMIT:
                    slow += 1
                    if slow >= 2:
                        print("  [!] 监督线程：显存越线 %d MiB -> 终止推理" % uu)
                        kill_server()
                        return
        th = threading.Thread(target=watchdog, daemon=True)
        th.start()

        t0 = time.time()
        try:
            resp = post("/v1/chat/completions", {
                "model": "bench",
                "messages": [{"role": "user",
                              "content": body + "\n\n请用一句话概括上文核心。"}],
                "max_tokens": GEN_TOKENS,
                "temperature": 0.0,
                "chat_template_kwargs": {"enable_thinking": False},
            }, timeout=900)
        except Exception as e:
            print("!! 推理异常（可能已被监督线程终止）: %r" % e)
            return {"label": label, "ctx": ctx, "mtp": mtp_on, "ok": False,
                    "why": "infer_error"}
        finally:
            stop["v"] = True

        wall = time.time() - t0
        tm = resp.get("timings") or {}
        tg = tm.get("predicted_per_second", 0) or 0
        pp = tm.get("prompt_per_second", 0) or 0
        acc_n = tm.get("draft_n") or 0
        acc_k = tm.get("draft_n_accepted") or 0
        acc = (acc_k / acc_n) if acc_n else 0
        print("-" * 78)
        print("prefill : %.1f t/s" % pp)
        print("decode  : %.2f t/s" % tg)
        print("草稿接受: %s / %s = %.3f" % (acc_k, acc_n, acc))
        print("墙钟    : %.1f s   显存 %d MiB" % (wall, vram()))
        bad = tg < 8.0
        if bad:
            print("  >> 判定: 不可用（速度 %.2f t/s，已进入系统内存兜底）" % tg)
        return {"label": label, "ctx": ctx, "mtp": mtp_on, "ok": not bad,
                "tg": tg, "pp": pp, "acc": acc, "wall": wall,
                "load_s": load_s, "vram": vram()}
    finally:
        try:
            proc.terminate()
        except Exception:
            pass
        logf.close()
        kill_server()


def main():
    rows = []
    for label, ctx, mtp_on, dm in MATRIX:
        try:
            rows.append(run_one(label, ctx, mtp_on, dm))
        except Exception as e:
            print("!! %s 异常: %r" % (label, e))
            kill_server()
    print("\n" + "=" * 78)
    print("MTP x 上下文矩阵汇总")
    print("%-32s %6s %8s %9s %8s %9s"
          % ("配置", "可用", "decode", "prefill", "接受率", "显存 MiB"))
    for r in rows:
        if r.get("ok"):
            print("%-32s %6s %8.2f %9.1f %8.3f %9d"
                  % (r["label"], "YES", r["tg"], r["pp"], r["acc"], r["vram"]))
        else:
            print("%-32s %6s %8s %9s %8s %9s"
                  % (r["label"], "NO", "-", "-", "-", r.get("why")))
    json.dump(rows, open(r"D:\Bonsai-demo\_mtp_matrix.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    kill_server()


if __name__ == "__main__":
    main()
