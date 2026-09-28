# -*- coding: utf-8 -*-
import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

def walk(root, depth=0, maxdepth=3, show_files=True):
    if depth > maxdepth:
        return
    try:
        items = sorted(os.listdir(root))
    except Exception:
        return
    for it in items:
        p = os.path.join(root, it)
        pad = '  ' * depth
        if os.path.isdir(p):
            print('%s[DIR] %s' % (pad, it))
            walk(p, depth + 1, maxdepth, show_files)
        else:
            sz = os.path.getsize(p)
            print('%s      %-46s %8d B' % (pad, it[:46], sz))

base = r'C:\Users\intpj\.workbuddy\connectors'
for sub in ['ab530a90-3f33-4775-a454-67a08e438f86', 'default', 'marketplace-meta', 'skills']:
    d = os.path.join(base, sub)
    print('=' * 78)
    print('### connectors/%s' % sub)
    print('=' * 78)
    if os.path.isdir(d):
        walk(d, 0, 3)
    else:
        print('(不存在)')
    print()

# 找所有可能的 MCP server 定义文件
print('=' * 78)
print('### 全盘搜索 MCP server 定义（含 ardot / miora / tdrive 字样）')
print('=' * 78)
roots = [r'C:\Users\intpj\.workbuddy', r'C:\Users\intpj\.codebuddy']
for r in roots:
    for dirpath, dirnames, filenames in os.walk(r):
        # 跳过巨大的缓存
        if any(x in dirpath for x in ['node_modules', '\\cache\\', 'marketplaces', 'app.asar']):
            continue
        if dirpath.count(os.sep) - r.count(os.sep) > 4:
            continue
        for f in filenames:
            if f.endswith(('.json', '.jsonc', '.yaml', '.yml')):
                fp = os.path.join(dirpath, f)
                try:
                    if os.path.getsize(fp) > 2_000_000:
                        continue
                    t = open(fp, encoding='utf-8', errors='ignore').read()
                except Exception:
                    continue
                if re.search(r'ardot|miora|tdrive|agent-earth|edgeone', t, re.I):
                    print('  %s  (%d B)' % (fp, len(t)))
