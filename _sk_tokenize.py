import json, sys, os, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
base = r'C:\Users\intpj\.workbuddy'
cache = json.load(open(os.path.join(base, '.skill-list-cache.json'), encoding='utf-8'))['results']
inj = [r for r in cache if not r.get('disable') and not r.get('disableModelInvocation')]

def build(rows):
    out = []
    for r in rows:
        out.append('- %s: %s (location: %s)' % (r.get('name') or '', r.get('description') or '', r.get('filePath') or ''))
    return '\n'.join(out)

def tok(text):
    body = json.dumps({'content': text}).encode('utf-8')
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request('http://127.0.0.1:8080/tokenize', data=body,
                                 headers={'Content-Type': 'application/json'})
    with op.open(req, timeout=60) as resp:
        d = json.loads(resp.read().decode('utf-8'))
    return len(d.get('tokens', []))

print('注入池总数:', len(inj))
for n in (50, 100, 150, 200, 300, 742):
    sub = inj[:n]
    t = build(sub)
    try:
        tk = tok(t)
        print('  取前 %3d 条 → %6d 字符 → %6d token   (%.1f token/条)' % (n, len(t), tk, tk / n))
    except Exception as e:
        print('  取前 %3d 条 → 失败: %s' % (n, e))
        break
