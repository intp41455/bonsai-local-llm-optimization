# -*- coding: utf-8 -*-
import json, sys, os, re, collections
sys.stdout.reconfigure(encoding='utf-8')

d2 = json.load(open(r'C:\Users\intpj\.workbuddy\.skill-list-cache.json', encoding='utf-8'))
res = [x for x in d2['results'] if isinstance(x, dict)]
inj = [x for x in res if not x.get('disableModelInvocation') and not x.get('disable')]
print('总技能 %d / 会注入 %d' % (len(res), len(inj)))

# 功能簇关键词（命中即归组）
GROUPS = {
    'PPT 演示文稿': ['ppt', 'pptx', '幻灯片', '演示文稿', 'slide', 'beamer'],
    'Excel / 表格': ['excel', 'xlsx', '表格', 'spreadsheet', 'csv', 'sheet'],
    'Word / 文档排版': ['docx', 'word 文档', '公文', '排版', '文档生成'],
    'PDF 处理': ['pdf'],
    '周报 / 汇报': ['周报', '月报', '日报', '汇报', 'report-generat'],
    '图像生成': ['文生图', 'text-to-image', '图片生成', '配图', 'image-gen', '海报', 'poster', 'men图标', '菜单图标'],
    '视频生成 / 剪辑': ['视频生成', '文生视频', 'video-gen', '剪辑', '视频续写'],
    '网页 / 前端开发': ['前端', 'frontend', '网页', 'html', '落地页', '网站'],
    '部署 / 上线': ['部署', '上线', '发布', 'deploy', 'cloudstudio', '发布为应用'],
    '爬虫 / 采集': ['爬虫', '抓取', '采集', 'scrape', 'crawl'],
    'SEO / 营销': ['seo', '营销', '获客', '私域', '推广'],
    '搜索 / 检索': ['搜索', '检索', 'search', 'deep-research', '深度研究', '调研'],
    '知识库 / 记忆': ['知识库', '记忆', 'memory', 'knowledge'],
    '命理 / 玄学': ['八字', '命理', '紫微', '占星', '塔罗', 'bazi', 'destiny'],
    '心理 / 咨询': ['心理', '咨询师', 'cbt', 'counsel'],
    '法律 / 合同': ['法律', '合同', 'contract', 'legal', '民法典'],
    '简历 / 求职': ['简历', '求职', '面试', 'jd', 'resume', 'interview', 'boss'],
    'HR / 绩效': ['hr', '绩效', '考勤', '招聘', '员工', '测评'],
    '文案 / 写作': ['文案', '写作', 'copywrit', 'humanizer', '去ai味', '公众号'],
    '脑图 / 拆书': ['脑图', 'mindmap', '拆书', '读书', 'book'],
    '浏览器自动化': ['browser', '浏览器', 'playwright', 'selenium'],
    '代码审查 / 质量': ['code-review', '代码审查', '重构', '测试'],
    '财务 / 投资': ['财务', '投资', '财报', '估值', '金融', '股票'],
    '翻译': ['翻译', 'translat'],
    'OCR / 识别': ['ocr', '识别', '文字提取'],
}

def toks(x):
    return (str(x.get('name') or '') + ' ' + str(x.get('description') or '')).lower()

hits = collections.defaultdict(list)
assigned = set()
for x in inj:
    t = toks(x)
    for g, kws in GROUPS.items():
        if any(k in t for k in kws):
            hits[g].append(x)
            assigned.add(id(x))
            break

print('\n=== 可注入技能按功能簇分布（仅列出 ≥3 个成员的簇）===')
for g, items in sorted(hits.items(), key=lambda x: -len(x[1])):
    if len(items) < 3:
        continue
    print('\n【%s】%d 个' % (g, len(items)))
    for x in items:
        print('    - %-44s  %s' % (str(x.get('name'))[:44], str(x.get('filePath'))[-52:]))

print('\n未归类: %d' % (len(inj) - len(assigned)))
