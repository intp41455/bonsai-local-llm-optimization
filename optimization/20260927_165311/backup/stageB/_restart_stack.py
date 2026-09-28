# -*- coding: utf-8 -*-
"""_restart_stack.py —— 探测僵死 -> 以最优配置重建整条链

WHY
    2026-09-27 12:21 的一次真实 Agent 请求把上游卡在 prefill 边界：GPU 100%
    空转、功耗仅 38W、显存 7728/8151 MiB 顶格，而
        llamacpp:prompt_seconds_total   379.796  (冻住)
        llamacpp:prompt_tokens_total    175077   (冻住)
        llamacpp:requests_processing    1        (冻住)
    连续 50 秒零增长 —— 该请求永远不会有结果。旧启动器只看"端口在不在监听"，
    会把僵尸一直沿用下去。

本脚本做三件事
    1) 探活：往上游发一个 max_tokens=1 的微型推理请求，超时即判定僵死；
    2) 重建：僵死则清掉 :8080/:8081 重起（含日志落盘，便于事后归因）；
    3) 对齐：代理带 --strip-location 启动，并用同一条瘦身管线重新预热 KV，
       保证前缀逐字节一致（否则预热白做）。

用法
    python -u _restart_stack.py            # 探活 + 按需重建 + 预热 + 起代理
    python -u _restart_stack.py --force    # 无条件重建
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

BIN = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo\bin"
MODEL = r"D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PY = r"C:\Users\intpj\AppData\Local\Programs\Python\Python310\python.exe"
DEMO = r"D:\Bonsai-demo"
LOGDIR = r"D:\Bonsai-demo\logs"
UP_LOG = os.path.join(LOGDIR, "llama-server.log")
PX_LOG = os.path.join(LOGDIR, "proxy.log")

UP_ARGS = [os.path.join(BIN, "llama-server.exe"), "-m", MODEL,
           "-ngl", "99", "-fa", "on", "-np", "1", "-c", "65536",
           "-b", "2048", "-ub", "512", "-ctk", "q4_0", "-ctv", "q4_0",
           "--backend-sampling", "--jinja", "--metrics",
           "--log-file", UP_LOG,
           "--host", "127.0.0.1", "--port", "8081", "--alias", "bonsai-2-27b"]

DETACH = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def kill_port(port):
    try:
        # 中文 Windows 的 netstat 输出是 GBK；不显式指定会按 UTF-8 解，直接炸。
        out = subprocess.run(["netstat", "-ano"], capture_output=True,
                             text=True, encoding="gbk", errors="replace",
                             timeout=30).stdout or ""
    except Exception as e:
        print("  netstat 失败:", e)
        return 0
    pids = set()
    for ln in out.splitlines():
        if (":%d " % port) in ln and "LISTENING" in ln:
            tok = ln.split()[-1]
            if tok.isdigit():
                pids.add(tok)
    for p in pids:
        print("  kill :%d  pid=%s" % (port, p))
        subprocess.run(["taskkill", "/f", "/pid", p], capture_output=True)
    return len(pids)


def probe_upstream(timeout=10):
    """发一个微型推理请求探活。僵死时它会排队卡住 -> 超时。"""
    body = json.dumps({"model": "bonsai-2-27b",
                       "messages": [{"role": "user", "content": "ping"}],
                       "max_tokens": 1, "stream": False}).encode()
    req = urllib.request.Request("http://127.0.0.1:8081/v1/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
        return True, time.time() - t0
    except Exception as e:
        return False, time.time() - t0


def wait_health(max_s=120):
    t0 = time.time()
    while time.time() - t0 < max_s:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8081/health", timeout=3) as r:
                if b"ok" in r.read():
                    return time.time() - t0
        except Exception:
            pass
        time.sleep(2)
    return None


def main():
    force = "--force" in sys.argv
    os.makedirs(LOGDIR, exist_ok=True)
    print("=" * 66)
    print(" Bonsai 栈重建（僵死探测 -> 最优配置重建）")
    print("=" * 66, flush=True)

    # ---------- 1) 探活 ----------
    need_up = True
    try:
        with urllib.request.urlopen("http://127.0.0.1:8081/health", timeout=3) as r:
            listening = b"ok" in r.read()
    except Exception:
        listening = False

    if listening and not force:
        print("[1/4] :8081 在监听，发微型请求探活（最长 10 秒）...", flush=True)
        ok, dt = probe_upstream(10)
        if ok:
            print("      健康：%.2f 秒响应。上游不用重建。" % dt, flush=True)
            need_up = False
        else:
            print("      !! %.1f 秒无响应 —— 判定僵死（GPU 空转）。清理重建。"
                  % dt, flush=True)
    elif force:
        print("[1/4] --force：无条件重建。", flush=True)

    # ---------- 2) 清理 ----------
    print("[2/4] 清理 :8080 / :8081 ...", flush=True)
    n = kill_port(8080) + kill_port(8081)
    if n:
        time.sleep(3)

    # ---------- 3) 起上游 ----------
    if need_up or force:
        print("[3/4] 启动 llama-server（日志 -> %s）..." % UP_LOG, flush=True)
        subprocess.Popen(UP_ARGS, creationflags=DETACH, close_fds=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        dt = wait_health(150)
        if dt is None:
            print("      !! 上游 150 秒未就绪，看日志：%s" % UP_LOG, flush=True)
            return 1
        print("      上游就绪（%.0f 秒）。" % dt, flush=True)
    else:
        print("[3/4] 复用已在运行的上游。", flush=True)

    # ---------- 4) 预热 ----------
    print("[4/4] 用【最新一份】真实请求体预热（含瘦身管线）...", flush=True)
    p = subprocess.run([PY, "-u", os.path.join(DEMO, "warm_kv.py")],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=DEMO)
    print(p.stdout or "", flush=True)
    if p.stderr:
        print("  [stderr]", p.stderr[-800:], flush=True)

    # ---------- 5) 起代理 ----------
    print("启动代理 :8080（--strip-location --effort medium，日志 -> %s）..."
          % PX_LOG, flush=True)
    with open(PX_LOG, "a", encoding="utf-8") as lf:
        subprocess.Popen([PY, "-u", os.path.join(DEMO, "proxy", "bonsai_proxy.py"),
                          "--port", "8080", "--upstream", "8081",
                          "--warm", "--effort", "medium"],
                         creationflags=DETACH, close_fds=True,
                         stdout=lf, stderr=subprocess.STDOUT, cwd=DEMO)
    time.sleep(3)
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=5) as r:
            print("代理 :8080 ->", r.read().decode()[:60], flush=True)
    except Exception as e:
        print("代理探活失败：", e, flush=True)
        return 1
    print("=" * 66)
    print(" 完成。WorkBuddy 指向 :8080，模型选 Bonsai 2 27B (本地)。")
    print("=" * 66, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
