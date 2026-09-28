# -*- coding: utf-8 -*-
import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

def tok(s):
    zh = len(re.findall(r'[\u4e00-\u9fff]', s))
    return int(zh * 0.65 + (len(s) - zh) * 0.27)

print('=== 校验 settings.json ===')
sp = r'C:\Users\intpj\.workbuddy\settings.json'
d = json.load(open(sp, encoding='utf-8'))
print('顶层键:', sorted(d.keys()))
print('skillOverrides 条目:', len(d['skillOverrides']))
NEW = ['computer-use-linux', 'kimi-websearch', 'chrome-bridge-automation',
       'ppt-beautify', 'stagehand-browser-cli', 'workbuddy-dev-dashen']
for k in NEW:
    print('  %-30s = %s' % (k, d['skillOverrides'].get(k)))
print('enabledPlugins 条目:', len(d['enabledPlugins']), '(应仍为 25)')
print('sandbox 键存在:', 'sandbox' in d)

print()
print('=== 校验 2 个 SKILL.md ===')
F = [r'C:\Users\intpj\.workbuddy\skills\agent-earth\skills\SKILL.md',
     r'C:\Users\intpj\.workbuddy\skills\neodata-financial-search\SKILL.md']
for fp in F:
    t = open(fp, encoding='utf-8').read()
    endf = t.find('\n---', 3)
    fm = t[:endf + 4]
    has = [l for l in fm.splitlines() if l.strip().startswith('disable:')]
    print('  %-56s %s' % (os.path.basename(os.path.dirname(fp)), has))
    print('     备份存在: %s' % os.path.isfile(fp + '.bak-dedup-20260927-041938'))

print()
print('=== 本次关闭的 8 个技能：省下多少 ===')
cache = json.load(open(r'C:\Users\intpj\.workbuddy\.skill-list-cache.json', encoding='utf-8'))
res = [x for x in cache['results'] if isinstance(x, dict)]
KEYS = set(NEW) | {'agent-earth', 'neodata-financial-search'}
tot = 0
seen = set()
for x in res:
    ok = x.get('overrideKey') in KEYS
    if ok and x['overrideKey'] in seen and x['overrideKey'] not in ('agent-earth', 'neodata-financial-search'):
        continue
    if ok:
        blob = str(x.get('name') or '') + str(x.get('description') or '') + str(x.get('filePath') or '')
        c = tok(blob)
        tot += c
        seen.add(x['overrideKey'])
        print('  %-44s ≈%5d tok' % (str(x.get('name'))[:44], c))
print('  ' + '-' * 56)
print('  %-44s ≈%5d tok' % ('合计（去重后实际省）', tot))
