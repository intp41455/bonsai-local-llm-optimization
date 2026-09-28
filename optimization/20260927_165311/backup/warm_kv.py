# -*- coding: utf-8 -*-
"""
warm_kv.py —— 单独预热 llama-server 的 KV 缓存

用途
    服务重启后，WorkBuddy 的首条消息要付 125 秒冷启动 prefill（57k token @454 t/s）。
    本脚本用上一份真实请求体先重放一次（max_tokens=1），把这 125 秒挪到没人等的时候。
    跑完再让 WorkBuddy 发消息，首字延迟从 ~125 秒降到 ~2 秒。

用法
    python warm_kv.py                     # 用 capture/ 里最新的请求体
    python warm_kv.py <path\\to\\req.json>
    python warm_kv.py --check             # 只体检：看当前缓存是冷的还是热的
    python warm_kv.py --effort medium     # 指定思考档位（默认自动读代理落盘的档位）

为什么必须对齐思考档位
    reasoning_effort 是拼在 system 消息最前面的，属于 prompt 前缀。
    预热用 xhigh、实际请求用 medium，前缀就不同 -> 缓存必然不命中 -> 预热白做。
    所以本脚本默认读 capture/effort.txt（代理启动时写入的生效档位）保持一致。
"""
import importlib.util
import os
import sys

PROXY = r"D:\Bonsai-demo\proxy\bonsai_proxy.py"
UPSTREAM = int(os.environ.get("BONSAI_UPSTREAM", "8081"))
EFFORT_FILE = r"D:\Bonsai-demo\capture\effort.txt"


def parse(argv):
    """手写解析：避免 --effort 的取值被当成位置参数（旧版的坑）。"""
    check = False
    effort = None
    path = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--check":
            check = True
        elif a == "--effort":
            i += 1
            effort = argv[i] if i < len(argv) else None
        elif not a.startswith("--"):
            path = a
        i += 1
    return check, effort, path


def load_proxy():
    spec = importlib.util.spec_from_file_location("bonsai_proxy_mod", PROXY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    check, effort, path = parse(sys.argv[1:])

    src = "--effort 参数"
    if effort is None and os.path.exists(EFFORT_FILE):
        try:
            effort = open(EFFORT_FILE, encoding="utf-8").read().strip() or None
            src = "capture/effort.txt（代理启动时写入）"
        except Exception:
            effort = None
    if effort in ("xhigh", ""):
        effort = None          # xhigh 就是模型默认档，不需要注入
        src = "模型默认档 xhigh"
    if not effort:
        src = "模型默认档 xhigh"

    print("=" * 62)
    print(" Bonsai KV 预热" + ("（体检模式）" if check else ""))
    print("   上游 :%d" % UPSTREAM)
    print("   思考档位: %s   <- %s" % (effort or "xhigh（默认）", src))
    print("=" * 62, flush=True)

    bp = load_proxy()

    class _A:
        pass

    a = _A()
    a.effort = effort
    bp.ARGS = a          # 让 prewarm 里的 apply_effort 用同一档位构造请求

    pn = bp.prewarm(path, UPSTREAM, "体检" if check else "预热")
    if pn is None:
        print("\n没拿到结果。检查 llama-server 是否在下游端口上。")
        return 1
    if check:
        print()
        if pn > 1000:
            print(">> 当前是【冷】的。再发消息要等约 %.0f 秒。" % (pn / 454.0))
        else:
            print(">> 当前是【热】的。发消息约 1~3 秒出首字。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
