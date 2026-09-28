import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\intpj\.workbuddy'
cache = json.load(open(os.path.join(base, '.skill-list-cache.json'), encoding='utf-8'))['results']
usage = json.load(open(os.path.join(base, 'usage-log.json'), encoding='utf-8'))

used = usage.get('skills', {})
print('使用记录里的技能数:', len(used))
print()

inj = [r for r in cache if not r.get('disable') and not r.get('disableModelInvocation')]
print('会注入的技能池:', len(inj))
print()

# 用过的技能 name 集合
used_names = set(used.keys())
def hit(r):
    cand = {r.get('name'), r.get('slug'), r.get('overrideKey')}
    return bool(cand & used_names)

hit_list = [r for r in inj if hit(r)]
print('池子里「有使用记录」的:', len(hit_list))
print()

print('=== 有使用记录的技能（按最后使用日）===')
rows = sorted(used.items(), key=lambda x: x[1].get('lastUsedDate', ''), reverse=True)
for k, v in rows:
    print('  %-34s last=%s  n=%d' % (k[:34], v.get('lastUsedDate'), len(v.get('recentDates', []))))
