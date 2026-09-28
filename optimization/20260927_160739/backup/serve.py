# -*- coding: utf-8 -*-
"""
Bonsai 2 27B (PTQ1_0 + MTP) 常驻服务启动器 + 冒烟测试
RTX 5060 Laptop 8GB / llama.cpp bonsai-combo sm_120a 原生构建

用法:
    python serve.py            # 启动服务（若未运行），等待就绪后退出（服务继续后台运行）
    python serve.py --smoke    # 启动 + 发一次真实推理请求验证
    python serve.py --stop     # 停止服务
"""
import os, sys, time, json, subprocess, urllib.request, urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT  = r"D:\Bonsai-demo\dist\bonsai2-8gb-combo"
BIN   = os.path.join(ROOT, "bin")
MODEL = r"D:\Bonsai-demo\models\bonsai2-gguf\27B\Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
KV_BIAS = r"D:\Bonsai-demo\models\bonsai2-gguf\27B\Bonsai-2-27B-kv-bias.gguf"
LOG   = r"D:\Bonsai-demo\serve.log"
PIDF  = r"D:\Bonsai-demo\serve.pid"

PORT = int(os.environ.get("BONSAI_PORT", "8080"))
CTX  = int(os.environ.get("BONSAI_CTX", "32768"))
BASE = "http://127.0.0.1:%d" % PORT

# Windows 进程创建标志：脱离父进程 + 独立进程组
DETACHED = 0x00000008 | 0x00000200


def build_args():
    args = [
        os.path.join(BIN, "llama-server.exe"),
        "-m", MODEL,
        "-ngl", "99", "-fa", "on", "-np", "1",
        "-c", str(CTX), "-b", "2048", "-ub", "512",
        "-ctk", "q4_0", "-ctv", "q4_0",
        "--spec-type", "draft-mtp",
        "--spec-draft-n-max", "1",
        "--spec-draft-depth-max", "4096",
        "-ctkd", "q4_0", "-ctvd", "q4_0",
        "--backend-sampling",
        "--jinja",
        "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
        "--reasoning-budget", "20480",
        "--reasoning-budget-message", "Now produce the complete answer.",
        "-n", "24576",
        "--temp", "1.0", "--top-p", "0.95", "--top-k", "20",
        "--host", "127.0.0.1", "--port", str(PORT),
        "--alias", "bonsai-2-27b",
        "--metrics",
    ]
    # KV 校准偏置：q4_0 KV 零解码代价精度修复（KV-CACHE.md）；不匹配时 loader 拒绝加载，删下两行即回退
    # Bonsai 2 无 drafter（SPECULATIVE.md）；draft-mtp 是唯一投机路径，n-max=1 为 8GB 实测最优
    if os.path.exists(KV_BIAS):
        args += ["--kv-mean-center", KV_BIAS]
    return args


def health(timeout=3):
    try:
        with urllib.request.urlopen(BASE + "/health", timeout=timeout) as r:
            return '"ok"' in r.read().decode("utf-8", "ignore")
    except Exception:
        return False


def start():
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"   # MTP 严格无损开关
    f = open(LOG, "wb")
    p = subprocess.Popen(
        build_args(), cwd=BIN, env=env,
        stdout=f, stderr=subprocess.STDOUT,
        creationflags=DETACHED, close_fds=True,
    )
    try:
        open(PIDF, "w").write(str(p.pid))
    except Exception:
        pass
    return p


def wait_ready(timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if health():
            return time.time() - t0
        # 进程是否已死
        if os.path.exists(PIDF):
            try:
                pid = int(open(PIDF).read().strip())
                # tasklist 输出为 GBK，必须显式指定编码，否则 text=True 会抛 UnicodeDecodeError
                out = subprocess.run(
                    ["tasklist", "/FI", "PID eq %d" % pid, "/NH", "/FO", "CSV"],
                    capture_output=True, encoding="gbk", errors="ignore")
                if str(pid) not in (out.stdout or ""):
                    print("[!] 服务进程已退出，最后 30 行日志：")
                    tail(30)
                    return None
            except Exception:
                pass
        time.sleep(1)
    return None


def tail(n=30):
    try:
        with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        for ln in lines[-n:]:
            print("   " + ln.rstrip())
    except Exception as e:
        print("   (读取日志失败: %s)" % e)


def stop():
    if not os.path.exists(PIDF):
        print("[i] 没有 PID 记录")
        return
    pid = int(open(PIDF).read().strip())
    r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                       capture_output=True, text=True)
    print("[stop]", r.stdout.strip() or r.stderr.strip())
    try:
        os.remove(PIDF)
    except Exception:
        pass


def smoke():
    body = {
        "model": "bonsai-2-27b",
        "messages": [{"role": "user", "content": "用一句话说明什么是三元量化（ternary quantization）。"}],
        "max_tokens": 128,
        "temperature": 0.7,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        BASE + "/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read().decode("utf-8"))
    dt = time.time() - t0

    msg = d.get("choices", [{}])[0].get("message", {}) or {}
    content = (msg.get("content") or "").strip()
    tm = d.get("timings", {}) or {}
    usage = d.get("usage", {}) or {}

    print()
    print("=" * 62)
    print("  冒烟测试结果")
    print("=" * 62)
    print("  回复内容 : %s" % (content[:200] if content else "(空)"))
    print("  总耗时   : %.2f s" % dt)
    print("  输入 token: %s" % usage.get("prompt_tokens", "?"))
    print("  输出 token: %s" % usage.get("completion_tokens", "?"))
    if tm:
        print("  prefill  : %.2f t/s" % tm.get("prompt_per_second", 0.0))
        print("  decode   : %.2f t/s" % tm.get("predicted_per_second", 0.0))
        if "draft_n" in tm:
            print("  草稿接受 : %s/%s" % (tm.get("draft_n_accepted", "?"), tm.get("draft_n", "?")))
    return d


def main():
    if "--stop" in sys.argv:
        stop()
        return

    print("=" * 62)
    print("  Bonsai 2 27B (PTQ1_0 + MTP) 8GB 常驻服务")
    print("=" * 62)

    if health():
        print("[i] 服务已在运行 %s" % BASE)
    else:
        if not os.path.exists(MODEL):
            print("[x] 模型文件不存在: %s" % MODEL)
            sys.exit(1)
        print("[1/2] 启动 llama-server (port %d, ctx %d) ..." % (PORT, CTX))
        p = start()
        print("      pid = %d" % p.pid)
        t = wait_ready()
        if t is None:
            print("[x] 启动失败或超时")
            sys.exit(1)
        print("      就绪，耗时 %.0f s" % t)

    # 显存 / 频率快照
    try:
        q = ("clocks.current.memory,clocks.current.sm,"
             "memory.used,memory.total,power.draw,temperature.gpu")
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=" + q, "--format=csv,noheader"],
            capture_output=True, text=True, timeout=15)
        print("[2/2] GPU: %s" % r.stdout.strip())
    except Exception as e:
        print("[2/2] GPU 查询失败: %s" % e)

    print()
    print("  接口地址 : %s/v1" % BASE)
    print("  模型别名 : bonsai-2-27b")
    print("  健康检查 : %s/health" % BASE)
    print("  服务日志 : %s" % LOG)

    if "--smoke" in sys.argv:
        smoke()
    else:
        print()
        print("  提示: 加 --smoke 参数可发一次真实推理验证")


if __name__ == "__main__":
    main()
