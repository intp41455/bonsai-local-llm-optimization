import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\intpj\.workbuddy\settings.json'
raw = open(p, encoding='utf-8').read()
print('文件大小: %d 字符' % len(raw))
d = json.loads(raw)
print('顶层键:' % ())
for k, v in d.items():
    t = type(v).__name__
    n = len(v) if hasattr(v, '__len__') else v
    print('  %-32s %-6s %s' % (k, t, str(n)[:40]))
print()
so = d.get('skillOverrides')
if so is not None:
    print('skillOverrides 条数:', len(so))
    items = list(so.items())[:5]
    for k, v in items:
        print('  %-40s %s' % (k[:40], json.dumps(v, ensure_ascii=False)))
    print('  ...')
    # 统计 disableModelInvocation 的数量
    n_dmi = sum(1 for v in so.values() if isinstance(v, dict) and v.get('disableModelInvocation'))
    print('其中 disableModelInvocation=true 的:', n_dmi)
    # 值的所有字段
    keys = set()
    for v in so.values():
        if isinstance(v, dict):
            keys |= set(v.keys())
    print('值的字段集合:', sorted(keys))
