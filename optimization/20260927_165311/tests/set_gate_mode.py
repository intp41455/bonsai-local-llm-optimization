# -*- coding: utf-8 -*-
r"""临时切换 config\bonsai-agent.json 的 budget.gate.mode（阶段 E 在线验证用）。

只做一处文本替换，保留原文件排版；替换前后都校验 JSON 合法。
用法: python set_gate_mode.py warn|reject
"""
import hashlib
import json
import sys

CFG = r"D:\Bonsai-demo\config\bonsai-agent.json"
sys.stdout.reconfigure(encoding="utf-8")


def main():
    want = (sys.argv[1] if len(sys.argv) > 1 else "").strip().lower()
    assert want in ("warn", "reject"), "用法: set_gate_mode.py warn|reject"
    s = open(CFG, "r", encoding="utf-8-sig").read()
    before = hashlib.sha256(s.encode("utf-8")).hexdigest()
    cur = json.loads(s)["budget"]["gate"]["mode"]
    if cur == want:
        print("已是 %s，无需改动（sha256=%s）" % (want, before[:16]))
        return 0
    old = '      "mode": "%s",' % cur
    assert s.count(old) == 1, "锚点命中 %d 次" % s.count(old)
    new = '      "mode": "%s",' % want
    s2 = s.replace(old, new)
    parsed = json.loads(s2)
    assert parsed["budget"]["gate"]["mode"] == want
    open(CFG, "w", encoding="utf-8", newline="\n").write(s2)
    print("gate.mode: %s -> %s   sha256 %s -> %s"
          % (cur, want, before[:16], hashlib.sha256(s2.encode("utf-8")).hexdigest()[:16]))
    return 0


if __name__ == "__main__":
    sys.exit(main())