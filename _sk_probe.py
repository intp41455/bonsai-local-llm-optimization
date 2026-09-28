import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\intpj\.workbuddy\.skill-list-cache.json'
print('size = %.2f MB' % (os.path.getsize(p) / 1048576))
d = json.load(open(p, encoding='utf-8'))
print('顶层类型:', type(d).__name__)
if isinstance(d, dict):
    for k, v in d.items():
        t = type(v).__name__
        n = len(v) if hasattr(v, '__len__') else v
        print('  key=%-24s %-6s %s' % (k, t, n))
    # 找技能数组
    for k, v in d.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print()
            print('>>> 列表字段:', k, '长度', len(v))
            print('    首条键:', list(v[0].keys()))
            print('    首条:', json.dumps(v[0], ensure_ascii=False)[:800])
