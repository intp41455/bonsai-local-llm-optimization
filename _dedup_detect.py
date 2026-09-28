# -*- coding: utf-8 -*-
"""近重复技能检测：描述/名称相似度 + 并查集聚类"""
import json, sys, re, collections, itertools
sys.stdout.reconfigure(encoding='utf-8')

cache = r'C:\Users\intpj\.workbuddy\.skill-list-cache.json'
d = json.load(open(cache, encoding='utf-8'))
res = [x for x in d['results'] if isinstance(x, dict)]
inj = [x for x in res if not x.get('disableModelInvocation') and not x.get('disable')]
print('总技能 %d  可注入 %d' % (len(res), len(inj)))

STOP = set('''the a an of to for and or in on with is are be as by at from that this it its
使用 用于 用户 需要 当 时 和 与 或 的 了 是 在 为 并 可 以 一个 进行 支持 帮助 生成 提供 工具 技能 自动 通过'''.split())

def sig(x):
    t = (str(x.get('name') or '') + ' ' + str(x.get('description') or '')).lower()
    en = set(re.findall(r'[a-z][a-z0-9\-]{2,}', t)) - STOP
    zh = set()
    for run in re.findall(r'[\u4e00-\u9fff]+', t):
        for i in range(len(run) - 1):
            bg = run[i:i + 2]
            if bg not in STOP:
                zh.add(bg)
    return en | zh, en

sigs = [sig(x) for x in inj]

parent = list(range(len(inj)))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb:
        parent[rb] = ra

TH = 0.42
edges = 0
for i, j in itertools.combinations(range(len(inj)), 2):
    A, Ae = sigs[i]
    B, Be = sigs[j]
    if not A or not B:
        continue
    # 英文名必须有一定交集，避免纯中文泛化
    if Ae and Be and not (Ae & Be):
        continue
    inter = len(A & B)
    if inter == 0:
        continue
    jac = inter / len(A | B)
    if jac >= TH:
        union(i, j)
        edges += 1

groups = collections.defaultdict(list)
for i in range(len(inj)):
    groups[find(i)].append(i)

clusters = [v for v in groups.values() if len(v) > 1]
clusters.sort(key=lambda v: -len(v))
print('相似对: %d   重复簇: %d   涉及技能: %d' % (edges, len(clusters), sum(len(c) for c in clusters)))
print()

out = []
for c in clusters:
    names = [inj[i] for i in c]
    out.append(names)
    print('【%d 个同功能】' % len(names))
    for x in names:
        print('    - %-46s  %s' % (str(x.get('name'))[:46], str(x.get('overrideKey') or '')))
    print()

json.dump([[{'name': x.get('name'), 'overrideKey': x.get('overrideKey'),
             'filePath': x.get('filePath'), 'desc': str(x.get('description'))[:220]} for x in c]
           for c in out],
          open(r'D:\Bonsai-demo\_dup_clusters.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
print('已写出 D:/Bonsai-demo/_dup_clusters.json')
