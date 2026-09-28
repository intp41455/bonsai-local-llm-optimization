# -*- coding: utf-8 -*-
import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\intpj\.workbuddy\connectors\ab530a90-3f33-4775-a454-67a08e438f86'
for f in ['connector-states.json', 'connector-states.v3.json', '.credentials.v3.json']:
    p = os.path.join(base, f)
    print('=' * 76)
    print('### %s' % f)
    print('=' * 76)
    try:
        d = json.load(open(p, encoding='utf-8'))
        print(json.dumps(d, ensure_ascii=False, indent=1)[:2600])
    except Exception as e:
        print('读取失败:', e)
    print()

print('=' * 76)
print('### connectors/default/mcp.json  —— 服务器键名与类型')
print('=' * 76)
p = r'C:\Users\intpj\.workbuddy\connectors\default\mcp.json'
d = json.load(open(p, encoding='utf-8'))
servers = d.get('mcpServers', d)
print('顶层键:', list(d.keys()))
print('服务器数:', len(servers))
print()
for name, cfg in servers.items():
    if not isinstance(cfg, dict):
        print('%-34s %s' % (name, str(cfg)[:80]))
        continue
    keys = list(cfg.keys())
    kind = cfg.get('type') or cfg.get('transport') or ('url' if 'url' in cfg else 'stdio')
    tgt = cfg.get('url') or cfg.get('command') or ''
    dis = cfg.get('disabled', cfg.get('enabled', '?'))
    print('%-34s type=%-8s disabled=%s' % (name[:34], kind, dis))
    print('      keys=%s' % keys)
    print('      target=%s' % str(tgt)[:120])
