# -*- coding: utf-8 -*-
"""审计：当前真正会被注入的技能池构成，以及要降到 N 条以内还需关多少。"""
import json, os, sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')
base = r'C:\Users\intpj\.workbuddy'
cache = json.load(open(os.path.join(base, '.skill-list-cache.json'), encoding='utf-8'))['results']
settings = json.load(open(os.path.join(base, 'settings.json'), encoding='utf-8'))
so = settings.get('skillOverrides', {})

print('技能缓存总条目 :', len(cache))
print('skillOverrides :', len(so))
print()

def injectable(r):
    if r.get('disable'): return False
    if r.get('disableModelInvocation'): return False
    return True

inj = [r for r in cache if injectable(r)]
print('原始可注入池   :', len(inj))

def still(r):
    k = r.get('overrideKey')
    if k and so.get(k) == 'user-invocable-only':
        return False
    return True

remain = [r for r in inj if still(r)]
off = [r for r in inj if not still(r)]
print('应用 overrides 后:', len(remain), ' （已软关', len(off), '）')
print()

def src(r):
    p = (r.get('filePath') or r.get('path') or '').replace('/', '\\').lower()
    if 'plugins' in p: return 'plugins/'
    if 'resources' in p and 'plugins' not in p: return 'resources(内置)'
    if p.startswith(r'c:\users\intpj\.workbuddy\skills'): return '.workbuddy/skills (用户级)'
    if '.workbuddy\\skills' in p: return '其他 .workbuddy/skills'
    return '其他: ' + (p[:60] or '(空)')

c = Counter(src(r) for r in remain)
print('=== 剩余池的来源分布 ===')
for k, v in c.most_common():
    print('  %-28s %4d' % (k, v))
print()

# 按顶层目录聚类 filePath 前缀
pref = Counter()
for r in remain:
    p = (r.get('filePath') or '')
    pref[p[:p.find('/', 40) + 1] if '/' in p[40:] else p[:70]] += 1
print('=== filePath 前缀 top 15 ===')
for k, v in pref.most_common(15):
    print('  %4d  %s' % (v, k))
print()

print('=== 样例（剩余池前 8 条）===')
for r in remain[:8]:
    print('  name=%-36s key=%-30s' % (str(r.get('name'))[:36], str(r.get('overrideKey'))[:30]))
    print('      path=%s' % r.get('filePath'))
print()

for target in (200, 160, 120, 100):
    need = len(remain) - target
    print('要降到 %3d 条：还需再软关 %d 条' % (target, need))
