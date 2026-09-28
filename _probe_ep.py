# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

cur = json.load(open(r'C:\Users\intpj\.workbuddy\settings.json', encoding='utf-8'))
bak = json.load(open(r'C:\Users\intpj\.workbuddy\settings.json.bak-dedup2-20260927-041938', encoding='utf-8'))
old = json.load(open(r'C:\Users\intpj\.workbuddy\settings.json.bak-dedup-20260927-041758', encoding='utf-8'))

for name, d in [('备份1 (04:17 我改前)', old), ('备份2 (04:19 我改前)', bak), ('当前', cur)]:
    print('=== %s ===' % name)
    print('  顶层键:', sorted(d.keys()))
    ep = d.get('enabledPlugins', {})
    print('  enabledPlugins: %d 条 (true=%d)' % (len(ep), sum(1 for v in ep.values() if v)))
    print('  skillOverrides: %d 条' % len(d.get('skillOverrides', {})))
    if 'pluginConfigs' in d:
        print('  pluginConfigs 键:', list(d['pluginConfigs'].keys()))
    print()

a, b, c = set(old.get('enabledPlugins', {})), set(bak.get('enabledPlugins', {})), set(cur.get('enabledPlugins', {}))
print('04:17 → 04:19 消失的插件:', sorted(a - b) or '(无)')
print('04:19 → 当前 消失的插件:', sorted(b - c) or '(无)')
print()
print('当前 enabledPlugins 明细:')
for k, v in sorted(cur['enabledPlugins'].items()):
    print('  %-52s %s' % (k, v))
