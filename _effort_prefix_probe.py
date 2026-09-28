# -*- coding: utf-8 -*-
"""直接渲染两种思考档位的 prompt，逐字节比对 —— 判定档位到底在不在 prompt 前缀里。"""
import json, sys, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8081"
BODY = json.load(open(r"D:\Bonsai-demo\capture\req_006_053121.json", encoding="utf-8"))


def render(kwargs):
    obj = {"messages": BODY["messages"]}
    if BODY.get("tools"):
        obj["tools"] = BODY["tools"]
    if kwargs is not None:
        obj["chat_template_kwargs"] = kwargs
    req = urllib.request.Request(BASE + "/apply-template",
        data=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["prompt"]


print("原请求体里自带的 chat_template_kwargs:", json.dumps(
    BODY.get("chat_template_kwargs"), ensure_ascii=False))
print("是否带 system 消息:", BODY["messages"][0]["role"],
      "| tools 数:", len(BODY.get("tools") or []))
print()

a = render(None)                                 # 不传 = 模板默认 xhigh
b = render({"reasoning_effort": "medium"})       # medium
c = render({"reasoning_effort": "xhigh"})        # 显式 xhigh
d = render({"enable_thinking": False})           # 关思考

n = min(len(a), len(b))
cp = 0
while cp < n and a[cp] == b[cp]:
    cp += 1

print("%-26s %8s %8s" % ("渲染结果", "字符数", "与'不传'差值"))
for tag, s in [("不传（默认 xhigh）", a), ("medium", b),
               ("显式 xhigh", c), ("enable_thinking=false", d)]:
    print("%-26s %8d %+8d" % (tag, len(s), len(s) - len(a)))
print()
print("・'不传' 与 'medium' 的公共前缀: %d 字符 / 总 %d 字符" % (cp, len(a)))
print("・'不传' 与 '显式 xhigh' 是否逐字节相同:", a == c)
print()
print("=== '不传'（=默认 xhigh）开头 260 字符 ===")
print(repr(a[:260]))
print()
print("=== 'medium' 开头 260 字符 ===")
print(repr(b[:260]))
print()
if a != b:
    lo = max(0, cp - 40)
    print("=== 第一个分叉点附近（字符 %d 起）===" % cp)
    print("  不传: ..." + repr(a[lo:cp + 80]))
    print("  medium: ..." + repr(b[lo:cp + 80]))
