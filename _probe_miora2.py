import json, sys, os, time
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\intpj\.workbuddy'
for f in ['mcp-tool-list.json', 'mcp-tool-policy.json', 'mcp-approvals.json']:
    p = os.path.join(base, f)
    print('%-26s %s  mtime=%s' % (f, os.path.getsize(p) if os.path.exists(p) else 'MISSING',
          time.strftime('%m-%d %H:%M:%S', time.localtime(os.path.getmtime(p))) if os.path.exists(p) else ''))
print()

d = json.load(open(os.path.join(base, 'mcp-tool-list.json'), encoding='utf-8'))
print('顶层键:', list(d.keys()))
ents = d.get('entries')
print('entries 类型:', type(ents).__name__, '数量:', len(ents) if hasattr(ents, '__len__') else '')
print()

if isinstance(ents, dict):
    for k, v in ents.items():
        s = json.dumps(v, ensure_ascii=False)
        print('--- key=%s  size=%d ---' % (k[:40], len(s)))
        print(s[:600])
        print()
