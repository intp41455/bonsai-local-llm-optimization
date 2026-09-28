import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\intpj\.workbuddy\.skill-list-cache.json'
d = json.load(open(p, encoding='utf-8'))
rows = d['results']

def will_inject(r):
    return (not r.get('disable')) and (not r.get('disableModelInvocation'))

inj = [r for r in rows if will_inject(r)]
print('总条目 %d  |  会注入 %d  |  已禁(disable) %d  |  不注入 %d'
      % (len(rows), len(inj),
         sum(1 for r in rows if r.get('disable')),
         sum(1 for r in rows if r.get('disableModelInvocation'))))
print()

# 领域关键词（按优先级顺序匹配）
DOMAINS = [
    ('命理玄学', ['命理','八字','紫微','占星','星盘','塔罗','周易','风水','星座','卜卦','奇门','六爻','紫微斗数','玄学','排盘']),
    ('人格测评/心理', ['mbti','人格','测评','disc','九型','心理','情绪','cbt','治疗','咨商','疗愈','依恋','焦虑','抑郁']),
    ('办公文档', ['docx','word','公文','文档','排版','纪要','汇报','周报','月报','公函','红头','合同文档','格式标准']),
    ('表格数据', ['excel','xlsx','表格','csv','透视','数据清洗','统计表','考勤','报表']),
    ('PPT/海报设计', ['ppt','幻灯片','演示','slide','deck','海报','版式','内刊','杂志','封面','排版设计','视觉设计','banner']),
    ('图像视频生成', ['图像生成','文生图','图生图','抠图','修图','视频生成','文生视频','3d模型','配音','字幕','ocr','去水印','美化']),
    ('开发/工程', ['代码','前端','后端','部署','网站','api','git','github','测试','架构','数据库','sql','重构','bug','编译','docker','小程序','app','接口']),
    ('AI/模型/推理', ['模型','推理','gguf','量化','gpu','cuda','本地大模型','提示词','prompt','agent','智能体','rag','向量','微调','skill','技能','mcp']),
    ('检索/研究', ['搜索','检索','调研','研究','知识库','论文','学术','文献','资料','爬','采集','监控','舆情']),
    ('电商跨境', ['电商','跨境','卖家','亚马逊','选品','店铺','淘宝','京东','拼多多','shopify','独立站','外贸']),
    ('医疗养老', ['药品','医疗','疾病','医院','养老','护理','老人','适老','健康管理','康复']),
    ('财税法律', ['财税','税务','发票','会计','记账','报销','合同审查','法律','民法典','合规','诉讼','劳动法']),
    ('投资金融', ['股票','基金','投资','估值','财报','金融','加密','期货','期权','市值','复盘','交易']),
    ('教育学习', ['课程','教学','学生','老师','考试','拆书','阅读','笔记','错题','论文写作','留学']),
    ('生活娱乐', ['旅游','美食','宠物','育儿','游戏','健身','穿搭','电影','音乐','菜谱','健康饮食']),
    ('系统工具', ['电脑','文件管理','清理','软件','系统设置','剪贴板','截图','输入法','浏览器','注册表','装机','磁盘']),
    ('沟通协作', ['邮件','日历','会议','微信','钉钉','飞书','消息','提醒','群聊','通知','日程']),
    ('内容创作', ['写作','文案','公众号','小红书','抖音','视频脚本','翻译','润色','标题','爆款','自媒体','播客']),
]

def classify(r):
    text = ((r.get('name') or '') + ' ' + (r.get('description') or '')).lower()
    for dom, kws in DOMAINS:
        for kw in kws:
            if kw in text:
                return dom
    return '未分类'

from collections import defaultdict
g = defaultdict(list)
for r in inj:
    g[classify(r)].append(r)

def cost(r):
    return (len(r.get('name') or '') + len(r.get('description') or '')) // 2 + 12

print('%-16s %5s %9s  %s' % ('领域', '数量', '≈token', '样例'))
print('-' * 100)
tot = 0
for dom, items in sorted(g.items(), key=lambda x: -sum(cost(r) for r in x[1])):
    c = sum(cost(r) for r in items)
    tot += c
    names = '、'.join((r.get('name') or '')[:14] for r in items[:4])
    print('%-16s %5d %9d  %s' % (dom, len(items), c, names))
print('-' * 100)
print('%-16s %5d %9d' % ('合计(会注入)', len(inj), tot))
print()
print('估算口径： (name 字符 + description 字符)/2 + 12  ≈ token')
