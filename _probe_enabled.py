# -*- coding: utf-8 -*-
import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\intpj\.workbuddy\connectors\default\mcp.json'
d = json.load(open(p, encoding='utf-8'))
servers = d['mcpServers']
print('总条目:', len(servers))

enabled, custom = [], []
for name, cfg in servers.items():
    if not isinstance(cfg, dict):
        continue
    dis = cfg.get('disabled')
    if dis is not True:
        enabled.append((name, cfg))
    if not name.startswith('connector:'):
        custom.append((name, cfg))

print()
print('=== 未禁用（disabled != True）的条目：%d 个 ===' % len(enabled))
for name, cfg in enabled:
    tgt = cfg.get('url') or cfg.get('command') or ''
    print('  %-40s type=%-16s disabled=%s' % (name[:40], cfg.get('type', '?'), cfg.get('disabled')))
    print('        -> %s' % str(tgt)[:110])
    for k in ('headers', 'env'):
        if k in cfg:
            print('        %s: %s' % (k, list(cfg[k].keys()) if isinstance(cfg[k], dict) else cfg[k]))

print()
print('=== 非 connector: 前缀（自定义 MCP）：%d 个 ===' % len(custom))
for name, cfg in custom:
    tgt = cfg.get('url') or cfg.get('command') or ''
    print('  %-40s type=%-16s disabled=%s' % (name[:40], cfg.get('type', '?'), cfg.get('disabled')))
    print('        -> %s' % str(tgt)[:120])

print()
print('=== 常见大厂 MCP 的启用情况核对 ===')
WATCH = ['ardot', 'miora', 'tdrive', 'tencent-docs', 'baidu', 'github', 'ima', 'agent-earth',
         'edgeone', 'sheet', 'weixinpay', 'mail', 'genie', 'dingtalk', 'zsxq', 'yx']
for name, cfg in servers.items():
    low = name.lower()
    for w in WATCH:
        if w in low:
            print('  %-42s disabled=%s  type=%s' % (name[:42], cfg.get('disabled') if isinstance(cfg, dict) else '?',
                                                    (cfg.get('type') if isinstance(cfg, dict) else '?')))
            break
