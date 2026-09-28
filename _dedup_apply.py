# -*- coding: utf-8 -*-
"""应用去重：settings.json skillOverrides(6) + 2 个 SKILL.md 加 disable: true"""
import json, sys, os, shutil, datetime
sys.stdout.reconfigure(encoding='utf-8')

TS = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
NEW_KEYS = ['computer-use-linux', 'kimi-websearch', 'chrome-bridge-automation',
            'ppt-beautify', 'stagehand-browser-cli', 'workbuddy-dev-dashen']
SKILLMD = [
    r'C:\Users\intpj\.workbuddy\skills\agent-earth\skills\SKILL.md',
    r'C:\Users\intpj\.workbuddy\skills\neodata-financial-search\SKILL.md',
]

# ---------- 1. settings.json ----------
sp = r'C:\Users\intpj\.workbuddy\settings.json'
shutil.copy2(sp, sp + '.bak-dedup2-' + TS)
t = open(sp, encoding='utf-8').read()
d0 = json.loads(t)
before = len(d0['skillOverrides'])

anchor = '"skillOverrides": {'
i = t.find(anchor)
assert i > 0, '未找到 skillOverrides'
ins_at = i + len(anchor)
add = ''.join('\n    "%s": "user-invocable-only",' % k for k in NEW_KEYS if k not in d0['skillOverrides'])
t2 = t[:ins_at] + add + t[ins_at:]

d1 = json.loads(t2)   # 校验
assert len(d1['skillOverrides']) == before + len([k for k in NEW_KEYS if k not in d0['skillOverrides']])
# 确认没动别的键
assert set(d1.keys()) == set(d0.keys())
for k in d0:
    if k != 'skillOverrides':
        assert d1[k] == d0[k], '键 %s 被改动' % k
open(sp, 'w', encoding='utf-8', newline='').write(t2)
print('[1] settings.json  ✓  skillOverrides %d → %d' % (before, len(d1['skillOverrides'])))
for k in NEW_KEYS:
    print('      + %s' % k)

# ---------- 2. SKILL.md ----------
print()
for fp in SKILLMD:
    if not os.path.isfile(fp):
        print('[2] ✗ 不存在: %s' % fp)
        continue
    txt = open(fp, encoding='utf-8', errors='ignore').read()
    shutil.copy2(fp, fp + '.bak-dedup-' + TS)
    lines = txt.split('\n')
    assert lines[0].strip() == '---', '无 frontmatter'
    # 找闭合 ---
    close = None
    for n in range(1, len(lines)):
        if lines[n].strip() == '---':
            close = n
            break
    assert close, '未找到闭合 ---'
    # 已有 disable: ?
    hit = None
    for n in range(1, close):
        if lines[n].strip().startswith('disable:'):
            hit = n
            break
    if hit is not None:
        lines[hit] = 'disable: true'
        act = '改为 true'
    else:
        lines.insert(close, 'disable: true')
        act = '插入'
    open(fp, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines))
    print('[2] %s  %s  → disable: true' % (act, os.path.basename(os.path.dirname(fp))))
    print('      %s' % fp)

print()
print('备份后缀: .bak-dedup2-%s / .bak-dedup-%s' % (TS, TS))
