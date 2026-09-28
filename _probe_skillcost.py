# -*- coding: utf-8 -*-
import json, sys, os, re, collections
sys.stdout.reconfigure(encoding='utf-8')

d2 = json.load(open(r'C:\Users\intpj\.workbuddy\.skill-list-cache.json', encoding='utf-8'))
res = d2['results']

def tok(s):
    zh = len(re.findall(r'[\u4e00-\u9fff]', s))
    return int(zh * 0.65 + (len(s) - zh) * 0.27)

stat = collections.defaultdict(lambda: [0, 0, 0])  # 组 -> [条数, 字符, token]
tot_cost = 0
for x in res:
    if not isinstance(x, dict):
        continue
    dm = bool(x.get('disableModelInvocation'))
    dis = bool(x.get('disable'))
    src = str(x.get('source') or '?')
    nm = str(x.get('name') or '')
    de = str(x.get('description') or '')
    # 注入时大致包含：name + description + location
    blob = nm + de + str(x.get('filePath') or '')
    c = len(blob)
    if dm or dis:
        stat['已关闭注入'][0] += 1
        stat['已关闭注入'][1] += c
        stat['已关闭注入'][2] += tok(blob)
    else:
        stat['会注入'][0] += 1
        stat['会注入'][1] += c
        stat['会注入'][2] += tok(blob)
    stat['  source=%s' % src]  # 占位

print('=== 技能注入状态 ===')
for k in ['会注入', '已关闭注入']:
    n, c, t = stat[k]
    print('  %-12s 条数=%-5d 字符=%-8d ≈token=%d' % (k, n, c, t))

inj = [x for x in res if isinstance(x, dict) and not x.get('disableModelInvocation') and not x.get('disable')]
print('\n会注入的技能数: %d' % len(inj))
print('注入清单实测总字符: %d  ≈ %d token' % (stat['会注入'][1], stat['会注入'][2]))

print('\n=== 按来源 ===')
srcs = collections.Counter()
for x in res:
    if isinstance(x, dict):
        srcs[str(x.get('source') or '?')] += 1
for k, v in srcs.most_common():
    print('  %-22s %d' % (k, v))

print('\n=== 注入清单里 description 最长的 15 个（token 大户）===')
big = sorted(inj, key=lambda x: -tok(str(x.get('description') or '')))[:15]
for x in big:
    print('  %-46s ≈%5d tok  %s' % (str(x.get('name'))[:46], tok(str(x.get('description') or '')),
                                    str(x.get('source'))))

print('\n=== source=userSettings 的注入项 (最多 40) ===')
u = [x for x in inj if x.get('source') == 'userSettings']
print('数量:', len(u))
for x in u[:40]:
    print('  %-46s ≈%4d  %s' % (str(x.get('name'))[:46], tok(str(x.get('description') or '')), str(x.get('filePath'))[-46:]))
