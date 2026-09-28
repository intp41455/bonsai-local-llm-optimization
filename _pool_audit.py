# -*- coding: utf-8 -*-
"""审计 WorkBuddy 技能注入池：来源分类 + 精确条数 + 与 skillOverrides 的关系。"""
import json, os, sys, glob, re
sys.stdout.reconfigure(encoding='utf-8')

HOME = r'C:\Users\intpj'
WB = os.path.join(HOME, '.workbuddy')

# ---------- 1. settings.json ----------
sv = os.path.join(WB, 'settings.json')
S = json.load(open(sv, encoding='utf-8'))
print('=== settings.json ===')
print('顶层键 :', list(S.keys()))
so = S.get('skillOverrides') or {}
from collections import Counter
print('skillOverrides :', len(so), Counter(so.values()))
ep = S.get('enabledPlugins')
print('enabledPlugins :', type(ep).__name__, len(ep) if ep is not None else 0)
if isinstance(ep, dict):
    on = [k for k, v in ep.items() if v]
    print('   启用插件 :', len(on))
    print('   ', on[:30])
# 找可能的技能上限键
cand = [k for k in S.keys() if re.search(r'skill|Skill|tool|Tool|inject|Inject|max|Max|limit|Limit', k)]
print('可疑键 :', cand)
for k in cand:
    print('   %s = %s' % (k, json.dumps(S[k], ensure_ascii=False)[:200]))

# ---------- 2. 全盘 SKILL.md ----------
print()
print('=== 全盘 SKILL.md 来源分布 ===')
roots = {
    'user-skills    ': os.path.join(WB, 'skills'),
    'user-plugin    ': os.path.join(WB, 'plugins'),
    'app-builtin    ': r'D:\下载的\WorkBuddy\resources\app.asar.unpacked\resources\plugins',
    'workspace      ': r'C:\Users\intpj\WorkBuddy\2026-09-26-18-59-35\.workbuddy\skills',
}
allsk = {}
for tag, root in roots.items():
    n = 0
    for p in glob.glob(os.path.join(root, '**', 'SKILL.md'), recursive=True):
        n += 1
        allsk[p] = tag.strip()
    print('%s : %d' % (tag, n))
print('合计 SKILL.md :', len(allsk))

# ---------- 3. frontmatter ----------
FM = re.compile(r'^---\s*\n(.*?)\n---', re.S)
rows = []
nodisable = 0
for p, tag in allsk.items():
    try:
        t = open(p, encoding='utf-8', errors='ignore').read()
    except Exception:
        continue
    m = FM.search(t)
    fm = m.group(1) if m else ''
    name = re.search(r'^name:\s*(.+)$', fm, re.M)
    desc = re.search(r'^description:\s*(.+)$', fm, re.M)
    dis = re.search(r'^disable(d)?:\s*(true|yes)', fm, re.M | re.I)
    rows.append({
        'path': p, 'src': tag,
        'name': (name.group(1).strip() if name else os.path.basename(os.path.dirname(p))),
        'desc': (desc.group(1).strip() if desc else ''),
        'disabled': bool(dis),
        'chars': len(t),
    })
    if dis:
        nodisable += 1
print('frontmatter 含 disable 的 :', nodisable)

# ---------- 4. 与 skillOverrides 对照 ----------
print()
print('=== 分类统计 ===')
for tag in ['user-skills', 'user-plugin', 'app-builtin', 'workspace']:
    sub = [r for r in rows if r['src'] == tag]
    print('%-16s %4d 条' % (tag, len(sub)))

# 检查 skillOverrides 的键是否能在 SKILL.md 里找到
dirs = {}
for p in allsk:
    dirs[os.path.basename(os.path.dirname(p))] = p
miss = [k for k in so.keys() if k not in dirs]
print()
print('skillOverrides 键数      :', len(so))
print('   能对上目录名的      :', len(so) - len(miss))
print('   对不上的（示例）    :', miss[:8])

# ---------- 5. 落地清单 ----------
json.dump(rows, open(r'D:\Bonsai-demo\_pool_rows.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print()
print('明细写入 _pool_rows.json')
