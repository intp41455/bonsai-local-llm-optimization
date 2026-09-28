# -*- coding: utf-8 -*-
import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

p2 = r'C:\Users\intpj\.workbuddy\.skill-list-cache.json'
raw = open(p2, encoding='utf-8').read()
print('文件大小: %d 字符 ≈ %d token(/4)' % (len(raw), len(raw) // 4))
d2 = json.loads(raw)
if isinstance(d2, dict):
    print('顶层键:', list(d2.keys()))
    for k, v in d2.items():
        n = len(v) if hasattr(v, '__len__') else v
        print('  %-26s %-6s %s' % (k, type(v).__name__, n))
    sk = d2.get('skills') or d2.get('list') or []
    if isinstance(sk, list) and sk:
        print('\n条目样例键:', list(sk[0].keys()) if isinstance(sk[0], dict) else type(sk[0]).__name__)
        print(json.dumps(sk[0], ensure_ascii=False)[:400])
        blob = json.dumps(sk, ensure_ascii=False)
        zh = len(re.findall(r'[\u4e00-\u9fff]', blob))
        tot = len(blob)
        tok = int(zh * 0.65 + (tot - zh) * 0.27)
        print('\n技能总数: %d' % len(sk))
        print('全量字符: %d   中文 %d 字' % (tot, zh))
        print('全量估算 token: %d' % tok)
        print('若注入 201 条（线性折算）: ≈ %d token' % int(tok * 201 / len(sk)))
        # 按来源分组
        src = {}
        for x in sk:
            if isinstance(x, dict):
                loc = str(x.get('location') or x.get('path') or '')
                key = '用户级(.workbuddy)' if '.workbuddy\\skills' in loc or '.workbuddy/skills' in loc else \
                      '内置(bundled)' if 'app.asar' in loc else \
                      '插件(plugins)' if 'plugins' in loc else '其他/未知'
            else:
                key = '其他/未知'
            src[key] = src.get(key, 0) + 1
        print('\n按来源分组:')
        for k, v in sorted(src.items(), key=lambda x: -x[1]):
            print('   %-24s %d' % (k, v))
