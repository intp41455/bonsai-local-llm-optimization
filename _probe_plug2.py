# -*- coding: utf-8 -*-
import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

s = json.load(open(r'C:\Users\intpj\.workbuddy\settings.json', encoding='utf-8'))

so = s.get('skillOverrides', {})
print('=== skillOverrides ===')
print('条目数:', len(so))
for k, v in list(so.items())[:80]:
    print('  %-50s %s' % (k[:50], json.dumps(v, ensure_ascii=False)[:70]))

print()
print('=== enabledPlugins 全量 ===')
ep = s.get('enabledPlugins', {})
for k, v in ep.items():
    print('  %-52s %s' % (k, v))
print('合计:', len(ep), ' 其中 true:', sum(1 for v in ep.values() if v))

print()
print('=== MCP App 插件 manifest ===')
base = r'C:\Users\intpj\.workbuddy\plugins\cache\workbuddy-builtin'
for name in ['mcp-ardot-mcp-app', 'mcp-miora']:
    d = os.path.join(base, name)
    if not os.path.isdir(d):
        print('%s: 不存在于 %s' % (name, base))
        continue
    ver = os.listdir(d)[0] if os.listdir(d) else None
    print('\n--- %s / %s ---' % (name, ver))
    if ver:
        vd = os.path.join(d, ver)
        for f in os.listdir(vd):
            print('    ', f)
        for mf in ['.codebuddy-plugin/plugin.json', 'plugin.json', '.mcp.json', 'mcp.json']:
            mp = os.path.join(vd, mf)
            if os.path.isfile(mp):
                print('    === %s ===' % mf)
                print(open(mp, encoding='utf-8', errors='ignore').read()[:1200])

print()
print('=== plugins/data 下各目录内容 ===')
dd = r'C:\Users\intpj\.workbuddy\plugins\data'
for x in os.listdir(dd):
    xp = os.path.join(dd, x)
    if os.path.isdir(xp):
        sub = os.listdir(xp)[:6]
        print('  %-34s %s' % (x, sub))
