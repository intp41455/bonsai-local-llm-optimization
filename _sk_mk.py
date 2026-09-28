import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\intpj\.workbuddy\.skill-list-cache.json'
rows = json.load(open(p, encoding='utf-8'))['results']
inj = [r for r in rows if not r.get('disable') and not r.get('disableModelInvocation')]

def cost(r):
    return (len(r.get('name') or '') + len(r.get('description') or '')) // 2 + 12

mk = [r for r in inj if (r.get('marketplaceSource') or r.get('source')) == 'marketplace']
mk.sort(key=cost, reverse=True)

# 目录归属统计：filePath 的倒数第二段
from collections import Counter
dirs = Counter()
for r in mk:
    fp = (r.get('filePath') or '').replace('/', '\\')
    parts = fp.split('\\')
    d = parts[-2] if len(parts) >= 2 else '?'
    dirs[d] += 1
print('=== marketplace 技能所属目录（Top 25）===')
for d, n in dirs.most_common(25):
    print('  %-46s %d' % (d[:46], n))
print('  ... 共 %d 个目录' % len(dirs))
print()

print('=== marketplace 技能名（全部 %d 个，按占用降序）===' % len(mk))
line = []
for r in mk:
    nm = (r.get('name') or '')
    line.append(nm)
    if len(line) == 3:
        print('  ' + ' | '.join(line))
        line = []
if line:
    print('  ' + ' | '.join(line))
