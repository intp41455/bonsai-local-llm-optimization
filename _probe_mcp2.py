# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\intpj\.workbuddy\mcp-tool-list.json'
d = json.load(open(p, encoding='utf-8'))
ents = d['entries']
print('条目数:', len(ents))
print('=' * 70)
for i, (k, v) in enumerate(ents.items()):
    s = json.dumps(v, ensure_ascii=False)
    print('[%02d] key=%s' % (i, k))
    print('     类型=%s  序列化长度=%d  ≈%d token' % (type(v).__name__, len(s), len(s) // 4))
    if isinstance(v, dict):
        print('     子键:', list(v.keys()))
        for kk, vv in v.items():
            vs = json.dumps(vv, ensure_ascii=False)
            if len(vs) > 200:
                print('        %s: %s ... (%d 字符)' % (kk, vs[:160], len(vs)))
            else:
                print('        %s: %s' % (kk, vs))
    else:
        print('     值:', s[:300])
    print('-' * 70)
