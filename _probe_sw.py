# -*- coding: utf-8 -*-
import json, sys, os, re, glob
sys.stdout.reconfigure(encoding='utf-8')

# ---------- 1. settings.json 里的 MCP / connector 相关键 ----------
sp = r'C:\Users\intpj\.workbuddy\settings.json'
s = json.load(open(sp, encoding='utf-8'))
print('=== settings.json 顶层键 (%d 个) ===' % len(s))
for k in sorted(s.keys()):
    v = s[k]
    t = type(v).__name__
    size = len(json.dumps(v, ensure_ascii=False))
    mark = ''
    if re.search(r'mcp|connector|plugin|tool|skill|ardot|miora|disable|enable', k, re.I):
        mark = '   <<<'
    print('  %-44s %-6s %7d 字符%s' % (k, t, size, mark))

print()
print('=== 与 MCP/工具开关相关的键，展开 ===')
for k in sorted(s.keys()):
    if re.search(r'mcp|connector|plugin|toolset|disabledTools|enabled', k, re.I):
        print('\n--- %s ---' % k)
        print(json.dumps(s[k], ensure_ascii=False, indent=1)[:1500])

# ---------- 2. 技能清单占用 ----------
print()
print()
sk_dirs = [
    (r'C:\Users\intpj\.workbuddy\skills', '用户级'),
]
for root, label in sk_dirs:
    if not os.path.isdir(root):
        print('%s 技能目录不存在: %s' % (label, root))
        continue
    names = []
    for entry in os.listdir(root):
        md = os.path.join(root, entry, 'SKILL.md')
        if os.path.isfile(md):
            names.append((entry, md))
    print('=== %s技能清单 ===' % label)
    print('技能数量:', len(names))
    tot_desc = 0
    tot_name = 0
    for entry, md in names:
        tot_name += len(entry)
        try:
            txt = open(md, encoding='utf-8', errors='ignore').read()
        except Exception:
            txt = ''
        m = re.search(r'^description:\s*(.+)$', txt, re.M)
        if m:
            tot_desc += len(m.group(1).strip())
    print('技能名总字符 : %d' % tot_name)
    print('description总字符: %d' % tot_desc)
    print('清单粗估 token : %d (名字≈0.3/字符, 描述≈0.45/字符)' % int(tot_name * 0.3 + tot_desc * 0.45))
