# -*- coding: utf-8 -*-
"""去重干跑：列出将执行的动作，不改任何文件"""
import json, sys, io
sys.stdout.reconfigure(encoding='utf-8')

TARGETS_OVERRIDE = [
    ('computer-use-linux', 'Computer Use Linux', 'Windows 机器用不到'),
    ('kimi-websearch', 'Kimi WebSearch', '与豆包 WebSearch 同功能，留豆包'),
    ('chrome-bridge-automation', 'Midscene …with Browser Bridge', '与基础版同功能'),
    ('ppt-beautify', 'PPT美化', '与 PPT设计 同功能，留 PPT设计'),
    ('stagehand-browser-cli', 'Stagehand Browser CLI', '与 playwright-cli 同功能'),
    ('workbuddy-dev-dashen', 'AI开发大神', '与 WorkBuddy 大神 同功能'),
]
TARGETS_SKILLMD = [
    (r'C:\Users\intpj\.workbuddy\skills\agent-earth\skills\SKILL.md', 'agent-earth（嵌套重复）',
     '与上层 agent-earth 同名同 key，无法用配置区分'),
    (r'C:\Users\intpj\.workbuddy\skills\neodata-financial-search\SKILL.md', 'NeoData金融搜索服务（用户级副本）',
     '与 finance-data 插件同名同 key，留插件版（会随插件更新）'),
]

p = r'C:\Users\intpj\.workbuddy\settings.json'
t = open(p, encoding='utf-8').read()
d = json.loads(t)
so = d['skillOverrides']
print('现有 skillOverrides 条目: %d' % len(so))
print()
print('=== 动作 1：写入 skillOverrides（保留原 136 条，新增下列） ===')
new = 0
for k, nm, why in TARGETS_OVERRIDE:
    st = '已存在，跳过' if k in so else '新增'
    if k not in so:
        new += 1
    print('  [%s] %-32s %-28s %s' % (st, k, nm, why))
print('  实际新增: %d 条' % new)

print()
print('=== 动作 2：改 SKILL.md frontmatter（加 disable: true） ===')
for fp, nm, why in TARGETS_SKILLMD:
    print('\n  ── %s' % nm)
    print('     %s' % fp)
    print('     原因: %s' % why)
    try:
        txt = open(fp, encoding='utf-8', errors='ignore').read()
    except Exception as e:
        print('     ✗ 读取失败: %s' % e)
        continue
    if not txt.startswith('---'):
        print('     ✗ 无 frontmatter，跳过')
        continue
    endf = txt.find('\n---', 3)
    fm = txt[:endf + 4]
    print('     frontmatter 长度 %d' % len(fm))
    print('     ---- 原文 ----')
    for line in fm.splitlines():
        print('       | ' + line)
    has = any(l.strip().startswith('disable:') for l in fm.splitlines())
    print('     现有 disable 字段: %s → %s' % (has, '改为 true' if has else '插入 disable: true'))

print()
print('=== 影响预估 ===')
print('  共关闭 8 个重复技能（6 个走配置 + 2 个走文件）')
print('  MCP 侧另有 miora / agent-earth 需你在连接器页手点')
