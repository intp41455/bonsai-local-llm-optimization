# -*- coding: utf-8 -*-
"""warm_kv.py —— 兼容入口（阶段 B 起改为委托统一启动管理器）

WHY
    阶段 B 起“预热”只有一个入口：launcher 的 prewarm 动作。
    本文件保留是为了不破坏现有调用（_restart_stack.py 等），
    本身不再重复实现预热逻辑，避免出现第二条预热管线。

用法（保持旧手感）
    python warm_kv.py            # = launcher prewarm（忙时自动跳过）
    python warm_kv.py --check    # 只体检：看当前缓存是冷是热
"""
import subprocess
import sys

PY = sys.executable
LAUNCHER = r"D:\Bonsai-demo\launcher\bonsai_launcher.py"


def main():
    args = sys.argv[1:]
    if "--check" in args:
        print("[i] 缓存体检已并入：launcher smoke（发一次有限推理，看冷/热）")
        return subprocess.call([PY, "-u", LAUNCHER, "smoke"])
    print("[i] warm_kv.py 已改为委托统一启动管理器（预热每次启动只做一次）")
    return subprocess.call([PY, "-u", LAUNCHER, "prewarm"])


if __name__ == "__main__":
    sys.exit(main())