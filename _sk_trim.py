import json, sys, os, shutil, time
sys.stdout.reconfigure(encoding='utf-8')

DRY = '--apply' not in sys.argv
base = r'C:\Users\intpj\.workbuddy'
sp = os.path.join(base, 'settings.json')

cache = json.load(open(os.path.join(base, '.skill-list-cache.json'), encoding='utf-8'))['results']
usage = json.load(open(os.path.join(base, 'usage-log.json'), encoding='utf-8')).get('skills', {})
settings = json.load(open(sp, encoding='utf-8'))

inj = [r for r in cache if not r.get('disable') and not r.get('disableModelInvocation')]

WHITE = [
 'skill-creator','find-skills','marketplace-skill-installer','expert-manager',
 'recommend-connectors','recommend-experts','skills-security-check','超级skill助手',
 '技能编排总纲','技能发现与选型索引','WorkBuddy专家生成器','Skill 制作助手',
 'workbuddy-prompt-slimming','技能项目开发文档','技能仓库 拉取执行 依赖镜像',
 'tencent-docs','tencent-docs-routing','tencent-docs-sheet-generation','tencent-docs-sheetagent',
 'tencent-docx','tencent-local-office-edit','tencent-pptx','tencent-saas-docs',
 '腾讯文档智能页面 · Smart Page','腾讯文档 PDFKit','腾讯ima','腾讯乐享',
 'destiny-master','無心堂起名','cantian-bazi','ziwei-doushu','vedic-astrology',
 '职业性格测评','职业能力测评','职业兴趣测评','职业锚测评','月度绩效考核表生成',
 '述职与绩效考核','绩效考核评语生成器','行为面试模拟教练','简历诊断',
 'Word 智能排版助手','doc-format-validator','docx-format-clone','html-to-docx',
 '文档智能比对','文档处理体系','Excel 表格处理','Excel 数据分析与自动化专家',
 'Excel 公式与数据整理','Office 文档引擎',
 '中文OCR','图片文字识别 OCR','视频内容识别与字幕提取','B站视频总结','视频截帧',
 '语音转写整理','本地文档与图片解析','微信WCDB本地解密与消息提取','PDF 文档处理',
 'ima-skill','ima-mcp','ima copilot 平台学习与实操指南',
 '前端开发','前端设计','后端模式','全栈开发','Agent 开发技能集','Web 应用测试',
 '发布为应用','EdgeOne Pages Deploy','腾讯云CloudBase','Cloudflare','高品质前端设计',
 '前端UI工程','CI/CD 自动化','发布上线','代码库上手',
 'ternary-gguf-8gb-deploy','llamacpp-vram-tuning','动动嘴改模型','私有化AI部署速查',
 '本地NPU文字识别','省 Token 任务路由器','byom-config',
 '微信数据查询 CLI（Windows 11）','微信聊天分析助手','钉钉套件','群聊转待办',
 '多平台内容采集助手',
 'canvas-design（视觉设计）','Infographic Maker','海报生成器（社媒封面/分享卡/OG图）',
 '杂志风网页PPT','瑞士风演示文稿','商务 HTML 演示文稿','PPT设计','ppt-implement',
 '可视化拆书助手','信息图制作',
 'ai-text-humanizer','去除AI味与提示词精简','提示词生成','长文本写作引擎','自然改写',
 'agent-browser','browser-e2e-static-site','agent-browser-e2e-verify','浏览器自动化',
 'github','github-push-via-api','Git 工作流','沙箱内拉取 GitHub 仓库',
 'html2pdf','html-to-pdf','网页转PDF导出（PDF/Word/MD/HTML）',
 '数据可视化报告生成','数据洞察分析师','数据库连接器','PowerBI运营分析',
 'project','深度研究智能体','free-api-wiring','omniroute__skillhub',
 'deep-research:research-en','multi-search-engine','init-cbc-sdk-web','fbs-bookwriter',
 '自我修正','经验循环','会议纪要','cloudstudio-deploy',
]

def norm(s):
    return (s or '').strip().lower().replace(' ', '').replace('_', '')

W = {norm(x) for x in WHITE}

def keep(r):
    nm = norm(r.get('name'))
    sl = norm(r.get('slug'))
    ok = norm(r.get('overrideKey'))
    if nm in W or sl in W or ok in W:
        return 'whitelist'
    for k in (r.get('name'), r.get('slug'), r.get('overrideKey')):
        if k in usage:
            return 'used'
    return ''

K = [r for r in inj if keep(r)]
D = [r for r in inj if not keep(r)]
print('注入池 %d  →  保留 %d  |  软关 %d' % (len(inj), len(K), len(D)))
print()
print('=== 保留清单（%d）===' % len(K))
nm = sorted((r.get('name') or '') for r in K)
for i in range(0, len(nm), 3):
    print('  ' + ' | '.join(nm[i:i+3]))
print()
# overrideKey 缺失 / 冲突检查
noKey = [r for r in D if not r.get('overrideKey')]
print('待软关中 overrideKey 为空的:', len(noKey), [r.get('name') for r in noKey[:5]])
from collections import Counter
kc = Counter(r.get('overrideKey') for r in K if r.get('overrideKey'))
conflict = [k for k, v in kc.items() if v > 1]
print('保留清单内 overrideKey 重复的:', len(conflict), conflict[:5])
print()

so = settings.setdefault('skillOverrides', {})
print('现有 skillOverrides:', len(so))
newkeys = [r['overrideKey'] for r in D if r.get('overrideKey')]
added = [k for k in newkeys if k not in so]
print('将新增:', len(added), ' 其中已存在的（跳过）:', len(newkeys) - len(added))
print('写入后预计条数:', len(so) + len(added))
print()

if DRY:
    print('*** DRY RUN —— 未写入。加 --apply 执行。***')
else:
    ts = time.strftime('%Y%m%d-%H%M%S')
    bak = sp + '.bak-trim-' + ts
    shutil.copy2(sp, bak)
    print('已备份:', os.path.basename(bak))
    for k in added:
        so[k] = 'user-invocable-only'
    with open(sp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
    print('已写入。skillOverrides 现有 %d 条。' % len(so))
