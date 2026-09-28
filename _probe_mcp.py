# -*- coding: utf-8 -*-
import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\intpj\.workbuddy\mcp-tool-list.json'
d = json.load(open(p, encoding='utf-8'))
print('顶层类型:', type(d).__name__)
if isinstance(d, dict):
    for k, v in d.items():
        print('  键:', k, '->', type(v).__name__, (len(v) if hasattr(v, '__len__') else v))
    ents = d.get('entries') or []
    print('\nentries 数:', len(ents))
    if ents:
        e0 = ents[0]
        print('第一条类型:', type(e0).__name__)
        s = json.dumps(e0, ensure_ascii=False)
        print('第一条前 1000 字符:\n', s[:1000])
        print('\n--- 每条 entry 的键集合 ---')
        keys = set()
        for e in ents:
            if isinstance(e, dict):
                keys |= set(e.keys())
        print(sorted(keys))
