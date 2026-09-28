import json, sys, os, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\intpj\.workbuddy'
sp = os.path.join(base, 'settings.json')
raw = open(sp, encoding='utf-8').read()
print('settings.json 大小: %d 字符 (%.1f KB)' % (len(raw), len(raw)/1024))
d = json.loads(raw)
so = d['skillOverrides']
print('JSON 合法 ✓   skillOverrides = %d 条' % len(so))
print('enabledPlugins =', len(d['enabledPlugins']))
print()

cache = json.load(open(os.path.join(base, '.skill-list-cache.json'), encoding='utf-8'))['results']
inj = [r for r in cache if not r.get('disable') and not r.get('disableModelInvocation')]

# 模拟应用：应用 skillOverrides 后的注入池
def will_inject(r):
    if r.get('disable'): return False
    k = r.get('overrideKey')
    if k and so.get(k) == 'user-invocable-only': return False
    if r.get('disableModelInvocation'): return False
    return True

remaining = [r for r in inj if will_inject(r)]
print('原注入池 %d  →  应用新配置后 %d' % (len(inj), len(remaining)))
print()

def tok(text):
    body = json.dumps({'content': text}).encode('utf-8')
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request('http://127.0.0.1:8080/tokenize', data=body,
                                 headers={'Content-Type': 'application/json'})
    with op.open(req, timeout=90) as resp:
        return len(json.loads(resp.read().decode('utf-8')).get('tokens', []))

def build(rows):
    return '\n'.join('- %s: %s (location: %s)' % (r.get('name') or '', r.get('description') or '', r.get('filePath') or '')
                     for r in rows)

print('=== 注入量对比（真实 tokenizer 实测）===')
old200 = tok(build(inj[:200]))
print('  收窄前：显示 200 条  → %6d token' % old200)
new_all = tok(build(remaining))
print('  收窄后：剩余 %3d 条全量 → %6d token' % (len(remaining), new_all))
print('  差额：%+d token' % (new_all - old200))
print()
print('注：剩余条数 %d，若系统展示上限为 200 条且 %d <= 200，则不再截断，全部展示。'
      % (len(remaining), len(remaining)))
