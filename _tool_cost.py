# -*- coding: utf-8 -*-
"""离线核算 tools 里每个连接器/MCP 的 token 成本（按字符估，不走 GPU）"""
import json, os, sys, re
sys.stdout.reconfigure(encoding='utf-8')

cap = r'D:\Bonsai-demo\capture'
d = json.load(open(os.path.join(cap, 'req_006_053121.json'), encoding='utf-8'))
tools = d['tools']

sysmsg = d['messages'][0]['content']
user1 = d['messages'][1]['content']

CH_PER_TOK = 3.5


def est(s):
    return int(round(len(s) / CH_PER_TOK))


print('=== 各部分字符/token 估算 ===')
print('%-28s %9s %8s' % ('部分', '字符', '≈token'))
print('-' * 50)
print('%-28s %9d %8d' % ('system', len(sysmsg), est(sysmsg)))
print('%-28s %9d %8d' % ('user[1] (摘要+reminder)', len(user1), est(user1)))
tj = json.dumps(tools, ensure_ascii=False)
print('%-28s %9d %8d' % ('tools (24个)', len(tj), est(tj)))
print('%-28s %9d %8d' % ('合计', len(sysmsg) + len(user1) + len(tj),
                          est(sysmsg) + est(user1) + est(tj)))
print()

# 按前缀归组
groups = {}
for t in tools:
    fn = (t.get('function') or {})
    name = fn.get('name') or t.get('name') or '?'
    if name.startswith('mcp__'):
        parts = name.split('__')
        key = 'mcp__' + parts[1] if len(parts) > 2 else name
    else:
        key = name
    groups.setdefault(key, []).append((name, len(json.dumps(t, ensure_ascii=False))))

rows = sorted(groups.items(), key=lambda kv: -sum(x[1] for x in kv[1]))
print('=== 按连接器/工具族归组（字符降序）===')
tot = 0
print('%-46s %4s %9s %8s' % ('连接器/工具', '个数', '字符', '≈token'))
print('-' * 72)
for k, items in rows:
    c = sum(x[1] for x in items)
    tot += c
    print('%-46s %4d %9d %8d' % (k, len(items), c, est('x' * c)))
print('-' * 72)
print('%-46s %4d %9d %8d' % ('TOTAL', len(tools), tot, est('x' * tot)))
print()

print('=== 明细（每个工具）===')
for k, items in rows:
    print('[%s]' % k)
    for n, c in sorted(items, key=lambda x: -x[1]):
        print('    %-52s %8d  ≈%6d tok' % (n[:52], c, est('x' * c)))
