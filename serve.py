# -*- coding: utf-8 -*-
"""serve.py —— 兼容入口（阶段 B 起改为委托统一启动管理器）

WHY
    本文件原先自行拼一套 llama-server 参数：
        -c 32768 / MTP ON / --reasoning-budget 20480 / -n 24576 / 直听 :8080
    与日常启动器（-c 65536 / MTP off / 后端 :8081 + 代理 :8080）不一致，
    属配置漂移（方案 P01）。现已统一：
        唯一权威配置 D:\\Bonsai-demo\\config\\bonsai-agent.json
        参数构造/启停 D:\\Bonsai-demo\\launcher\\bonsai_launcher.py
    本文件不再构造任何后端参数，只把旧用法映射过去。

用法（保持旧手感）
    python serve.py            # = launcher up
    python serve.py --smoke    # = launcher up --smoke
    python serve.py --stop     # = launcher stop（后端忙时会被拒绝）
"""
import subprocess
import sys

PY = sys.executable
LAUNCHER = r"D:\Bonsai-demo\launcher\bonsai_launcher.py"


def main():
    args = sys.argv[1:]
    if "--stop" in args:
        action = ["stop"]
    elif "--smoke" in args:
        action = ["up", "--smoke"]
    elif "--status" in args:
        action = ["status"]
    else:
        action = ["up"]
    print("[i] serve.py 已改为委托统一启动管理器：launcher\\bonsai_launcher.py %s"
          % " ".join(action))
    return subprocess.call([PY, "-u", LAUNCHER] + action)


if __name__ == "__main__":
    sys.exit(main())