import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

base = r'C:\Users\intpj\.workbuddy'
cache = json.load(open(os.path.join(base, '.skill-list-cache.json'), encoding='utf-8'))['results']
usage = json.load(open(os.path.join(base, 'usage-log.json'), encoding='utf-8')).get('skills', {})
inj = [r for r in cache if not r.get('disable') and not r.get('disableModelInvocation')]

used = set(usage.keys())

# ===== 白名单规则：只匹配 name / slug / overrideKey，不匹配描述 =====
KEEP = [
    # 平台元技能
    'skill-creator','find-skills','marketplace-skill','expert-manager','recommend-','skills-security',
    'skill 制作','skill制作','超级skill','技能编排','技能仓库','技能项目','skill 发布','skill 升级','skill 说明',
    'skill 助手','经验循环','自我修正','项目记忆','workbuddy专家','agent-dev','ai-ready','byom','动动嘴',
    # 腾讯文档生态
    'tencent','腾讯','文档智能','smart-page',
    # 命理
    '命理','八字','紫微','占星','星盘','排盘','destiny','塔罗','七政','bazi','ziwei','astrology','無心堂','奇门','六爻','玄',
    # 测评 / HR
    'mbti','人格','测评','disc','九型','big5','big five','职业','招聘','面试','简历','员工','绩效','人才','组织','hr ',
    # 办公文档
    'docx','word','文档','公文','排版','模板','纪要','报告','周报','月报','ppt','幻灯片','演示','excel','表格','考勤','格式','比对','校对','合同',
    # OCR / 视频 / 知识库
    'ocr','字幕','转写','视频','知识库','ima','语音','bilibili',
    # 开发 / 部署 / Agent
    'agent','智能体','前端','后端','部署','网站','小程序','api','爬','采集','自动化','浏览器','代码','数据库','git','github','cloudbase','cloudflare','edgeone','发布','沙箱','test','测试',
    # 本地 AI / 模型
    'gguf','量化','推理','模型','gpu','cuda','llama','提示词','prompt','微调','token','算力','npn','np',
    # 微信 / 协作
    '微信','飞书','钉钉','邮件','会议','群聊','dws',
    # 设计 / 图像（内刊）
    '设计','海报','版式','内刊','杂志','封面','图文','图像','配图','美化','抠图','infographic','canvas','draw','mermaid','excalidraw','ppt',
    # 数据 / 分析
    '数据','分析','可视化','图表','报表','统计','bi',
    # 通用写作
    '写作','文案','翻译','润色','改写','ai味','去ai',
    # 自建
    'ternary','bonsai','workbuddy-prompt','prompt-slimming','doc-format',
]

def keep(r):
    key = ' '.join(str(r.get(k) or '') for k in ('name','slug','overrideKey')).lower()
    if (r.get('name') in used) or (r.get('slug') in used) or (r.get('overrideKey') in used):
        return True, '有使用记录'
    for kw in KEEP:
        if kw.lower() in key:
            return True, kw
    return False, ''

K, D = [], []
for r in inj:
    ok, why = keep(r)
    (K if ok else D).append((r, why))

print('注入池 %d  →  建议保留 %d  |  建议软关 %d' % (len(inj), len(K), len(D)))
print()

from collections import Counter
c = Counter(w for _, w in K if w and w != '有使用记录')
print('=== 保留命中的关键词 Top 20 ===')
for w, n in c.most_common(20):
    print('  %-18s %d' % (w, n))
print()

print('=== 建议保留清单（%d 个）===' % len(K))
names = sorted((r.get('name') or '') for r, _ in K)
for i in range(0, len(names), 4):
    print('  ' + ' | '.join(names[i:i+4]))
