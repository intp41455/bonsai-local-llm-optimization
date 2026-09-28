# -*- coding: utf-8 -*-
import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

print('=' * 76)
print('### connectors/default/mcp.json —— 服务器清单')
print('=' * 76)
p = r'C:\Users\intpj\.workbuddy\connectors\default\mcp.json'
d = json.load(open(p, encoding='utf-8'))
print('顶层键:', list(d.keys()))
servers = d.get('mcpServers') or d
print('服务器数:', len(servers))
for name, cfg in (servers.items() if isinstance(servers, dict) else []):
    if isinstance(cfg, dict):
        tgt = cfg.get('url') or cfg.get('command') or ''
        print('  %-32s type=%-10s disabled=%s' % (name[:32], cfg.get('type', '?'), cfg.get('disabled', cfg.get('enabled', '-'))))
        print('        -> %s' % str(tgt)[:110])
    else:
        print('  %-32s %s' % (name[:32], str(cfg)[:70]))

print()
print('=' * 76)
print('### 技能缓存结构 ~/.workbuddy/.skill-list-cache.json')
print('=' * 76)
p2 = r'C:\Users\intpj\.workbuddy\.skill-list-cache.json'
d2 = json.load(open(p2, encoding='utf-8'))
print('顶层键:', list(d2.keys()) if isinstance(d2, dict) else type(d2).__name__)
if isinstance(d2, dict):
    for k, v in d2.items():
        n = len(v) if hasattr(v, '__len__') else ''
        print('  %-24s %-6s %s' % (k, type(v).__name__, n))
    sk = d2.get('skills') or []
    if sk and isinstance(sk, list):
        s0 = sk[0]
        print('\n技能条目样例键:', list(s0.keys()) if isinstance(s0, dict) else type(s0).__name__)
        print(json.dumps(s0, ensure_ascii=False)[:500])
        # 统计
        tot = 0
        for x in sk:
            tot += len(json.dumps(x, ensure_ascii=False))
        print('\n技能总数: %d   全量序列化: %d 字符' % (len(sk), tot))
        zh = len(re.findall(r'[\u4e00-\u9fff]', json.dumps(sk, ensure_ascii=False)))
        print('其中中文 %d 字  →  全量 ≈ %d token' % (zh, int(zh * 0.65 + (tot - zh) * 0.27)))
        print('按 201/816 比例折算注入量 ≈ %d token' % int(int(zh * 0.65 + (tot - zh) * 0.27) * 201 / max(1, len(sk))))
