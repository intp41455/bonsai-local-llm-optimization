# -*- coding: utf-8 -*-
import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\intpj\.workbuddy\plugins'

for f in ['installed_plugins.json', 'known_marketplaces.json']:
    p = os.path.join(base, f)
    print('=== %s ===' % f)
    if os.path.isfile(p):
        try:
            d = json.load(open(p, encoding='utf-8'))
            print(json.dumps(d, ensure_ascii=False, indent=1)[:2500])
        except Exception as e:
            print('解析失败:', e)
    else:
        print('(不存在)')
    print()

print('=== plugins/data ===')
dd = os.path.join(base, 'data')
if os.path.isdir(dd):
    for x in os.listdir(dd)[:40]:
        print('  ', x)

print()
print('=== skillOverrides (前 60 行) ===')
s = json.load(open(r'C:\Users\intpj\.workbuddy\settings.json', encoding='utf-8'))
so = s.get('skillOverrides', {})
print('条目数:', len(so))
keys = list(so.keys())
for k in keys[:60]:
    print('  %-46s %s' % (k[:46], json.dumps(so[k], ensure_ascii=False)[:80]))

print()
print('=== 统计 skillOverrides 里 false/disable 的条目 ===')
dis = [k for k, v in so.items() if v is False or (isinstance(v, dict) and v.get('enabled') is False)]
print('被禁用数:', len(dis))
for k in dis[:40]:
    print('  ', k)
