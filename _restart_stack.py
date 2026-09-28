# -*- coding: utf-8 -*-
"""_restart_stack.py —— 兼容入口（阶段 B 起改为委托统一启动管理器）

WHY
    原实现是方案 P07 的典型样本，并且叠了三处问题：
      1) 10 秒微型推理探活失败就判定“僵死” -> 按端口 taskkill :8080/:8081；
         单槽服务里的探活可能自己排队，健康的长任务会被误杀。
      2) warm_kv.py 预热一次，代理又带 --warm 预热一次（重复预热）。
      3) 自带一套后端参数（含 --log-file），又一处配置漂移。
    阶段 B 起全部交给 launcher：
      - 探活：/health + 进程身份 + /slots；忙时不探活、不重启；
      - 停止：只按记录并核对过身份的 PID，先请正常退出再考虑强制；
      - 预热：每次启动只做一次，且忙时跳过。

用法
    python -u _restart_stack.py           # = launcher up（必要时受控重启）
    python -u _restart_stack.py --force   # = 先 stop --force 再 up（无条件重建）
"""
import subprocess
import sys

PY = sys.executable
LAUNCHER = r"D:\Bonsai-demo\launcher\bonsai_launcher.py"


def main():
    args = sys.argv[1:]
    print("[i] _restart_stack.py 已改为委托统一启动管理器：launcher\\bonsai_launcher.py")
    if "--force" in args:
        subprocess.call([PY, "-u", LAUNCHER, "stop", "--force"])
    return subprocess.call([PY, "-u", LAUNCHER, "up"])


if __name__ == "__main__":
    sys.exit(main())