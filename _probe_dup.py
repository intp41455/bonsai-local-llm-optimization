# -*- coding: utf-8 -*-
import json, sys, os, re, collections
sys.stdout.reconfigure(encoding='utf-8')

# ---------- 1. usage-log 看真实请求 ----------
p = r'C:\Users\intpj\.workbuddy\usage-log.json'
try:
    d = json.load(open(p, encoding='utf-8'))
    print('=== usage-log.json ===')
    items = d if isinstance(d, list) else (d.get('entries') or d.get('logs') or [])
    if isinstance(d, dict):
        print('顶层键:', list(d.keys()))
    print('记录数:', len(items) if hasattr(items, '__len__') else '?')
    for it in (items[-4:] if isinstance(items, list) else []):
        s = json.dumps(it, ensure_ascii=False)
        print('  ', s[:400])
except Exception as e:
    print('usage-log 读取失败:', e)

# ---------- 2. 技能重名分析 ----------
print()
print('=== 技能清单重名/近重复分析 ===')
cache = r'C:\Users\intpj\.workbuddy\.skill-list-cache.json'
d2 = json.load(open(cache, encoding='utf-8'))
res = d2.get('results', [])
print('缓存条目数:', len(res))
if res and isinstance(res[0], dict):
    print('样例键:', list(res[0].keys()))
    print(json.dumps(res[0], ensure_ascii=False)[:300])

# 归一化名字：去掉 __skillhub 等后缀
def norm(n):
    return re.sub(r'(__skillhub|_skillhub|-skillhub)$', '', str(n).lower())

buckets = collections.defaultdict(list)
for x in res:
    if not isinstance(x, dict):
        continue
    nm = x.get('name') or x.get('skillName') or x.get('id') or ''
    buckets[norm(nm)].append(nm)

dups = {k: v for k, v in buckets.items() if len(v) > 1}
print('\n归一化后重名组数:', len(dups), ' 涉及条目:', sum(len(v) for v in dups.values()))
for k, v in sorted(dups.items(), key=lambda x: -len(x[1]))[:25]:
    print('  %-40s %s' % (k[:40], v))
