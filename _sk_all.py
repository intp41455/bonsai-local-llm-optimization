import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\intpj\.workbuddy\.skill-list-cache.json'
rows = json.load(open(p, encoding='utf-8'))['results']
inj = [r for r in rows if not r.get('disable') and not r.get('disableModelInvocation')]

def cost(r):
    return (len(r.get('name') or '') + len(r.get('description') or '')) // 2 + 12

# 按来源市场分组
from collections import defaultdict
src = defaultdict(lambda: [0, 0])
for r in inj:
    k = r.get('marketplaceSource') or r.get('source') or '?'
    src[k][0] += 1
    src[k][1] += cost(r)
print('=== 按来源市场 ===')
for k, (n, c) in sorted(src.items(), key=lambda x: -x[1][1]):
    print('%-18s %4d 个  ≈%6d token' % (k, n, c))
print()

# 名字长度分布 / 描述为空的比例
empty_desc = sum(1 for r in inj if not (r.get('description') or '').strip())
print('描述为空的技能:', empty_desc)
print()

# 全部技能名（按 token 降序），紧凑输出
inj.sort(key=cost, reverse=True)
print('=== 全部 %d 个技能（按占用降序，name | 描述前40字）===' % len(inj))
for i, r in enumerate(inj, 1):
    nm = (r.get('name') or '')[:30]
    ds = (r.get('description') or '').replace('\n', ' ')[:40]
    print('%3d %5d %-30s %s' % (i, cost(r), nm, ds))
