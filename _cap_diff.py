# -*- coding: utf-8 -*-
"""用 llama-server 的 /apply-template 做精确前缀比对 + 分词计数"""
import json, glob, os, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'http://127.0.0.1:8081'
cap = r'D:\Bonsai-demo\capture'


def post(path, obj, timeout=600):
    data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def ntokens(s):
    if not s:
        return 0
    try:
        return len(post('/tokenize', {'content': s})['tokens'])
    except Exception as e:
        return -1


def load(name):
    d = json.load(open(os.path.join(cap, name), encoding='utf-8'))
    req = {'messages': d['messages']}
    if d.get('tools'):
        req['tools'] = d['tools']
    return d, req


order = ['req_004_052534.json', 'req_005_052847.json', 'req_006_053121.json']
bodies, prompts = [], []
for n in order:
    d, req = load(n)
    bodies.append(d)
    p = post('/apply-template', req)['prompt']
    prompts.append(p)
    print('%s  渲染后 prompt = %d 字符' % (n, len(p)))

print()

# 精确分词
tok = [ntokens(p) for p in prompts]
for i, n in enumerate(order):
    print('%-24s prompt = %6d tokens' % (n, tok[i]))
print()

# 逐字节公共前缀
print('=' * 78)
print('【逐字节公共前缀分析】')
for i in range(len(prompts) - 1):
    a, b = prompts[i], prompts[i + 1]
    m = min(len(a), len(b))
    k = 0
    while k < m and a[k] == b[k]:
        k += 1
    common = a[:k]
    ct = ntokens(common)
    print('-' * 78)
    print('%s  ->  %s' % (order[i], order[i + 1]))
    print('  公共前缀        : %d 字符 / %d tokens' % (k, ct))
    print('  新 prompt 总量  : %d tokens' % tok[i + 1])
    if tok[i + 1] > 0:
        print('  理论复用率      : %.1f%%   （仅新增 %d tokens 需 prefill）'
              % (100.0 * ct / tok[i + 1], tok[i + 1] - ct))
    print('  分歧点上下文 :')
    print('    A: ...%s' % a[max(0, k - 120):k].replace('\n', '\\n'))
    print('       >>> %s' % a[k:k + 160].replace('\n', '\\n'))
    print('    B: ...%s' % b[max(0, k - 120):k].replace('\n', '\\n'))
    print('       >>> %s' % b[k:k + 160].replace('\n', '\\n'))

# 找所有 current_time 位置
print()
print('=' * 78)
print('【<current_time> 在 prompt 中的位置】')
for i, p in enumerate(prompts):
    idx, hits = 0, []
    while True:
        j = p.find('current_time', idx)
        if j < 0:
            break
        seg = p[j:j + 90].replace('\n', '\\n')
        hits.append((j, seg))
        idx = j + 1
    print('%s  (prompt %d 字符)' % (order[i], len(p)))
    for j, seg in hits:
        print('   @%-7d (%.1f%%)  %s' % (j, 100.0 * j / len(p), seg))
