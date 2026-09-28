# -*- coding: utf-8 -*-
import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')

p = r'C:\Users\intpj\.workbuddy\mcp-tool-list.json'
d = json.load(open(p, encoding='utf-8'))
ents = d['entries']

# 关键词 -> 服务名推断
SIGNS = [
    (['GetMe', 'SendMessage', 'ListMessages', 'SearchMessages', 'ForwardMessage'], 'agent-mail'),
    (['workbuddy_cloudservice'], 'genie-baas (云服务)'),
    (['tdrive.'], '腾讯文档 tdrive'),
    (['batch_edit', 'create_design', 'open_design'], 'ardot (设计画布)'),
    (['file_video_list', 'make_dir', 'get_quota'], '网盘 (baidu/微云)'),
    (['ExecuteTool', 'RecommendTools', 'GetAccountOverview'], 'agent-earth'),
    (['deploy_folder', 'deploy_zip'], 'EdgeOne Pages'),
    (['resolve_local_excel', 'run_command', 'read_table'], 'sheetagent'),
    (['miora_'], 'miora (多模态生成)'),
    (['weixinpay_'], 'weixinpay'),
    (['add_issue_comment', 'create_pull_request', 'search_code'], 'github'),
    (['import_urls', 'add_knowledge', 'search_knowledge'], 'ima (知识库)'),
]

rows = []
for k, v in ents.items():
    if not isinstance(v, list):
        continue
    names = [t.get('name', '?') for t in v if isinstance(t, dict)]
    blob = ' '.join(names)
    guess = '?'
    for keys, label in SIGNS:
        if any(s in blob for s in keys):
            guess = label
            break
    # 精确 token 估算：描述文本按中英混合权重
    chars = len(json.dumps(v, ensure_ascii=False))
    zh = len(re.findall(r'[\u4e00-\u9fff]', json.dumps(v, ensure_ascii=False)))
    en_chars = chars - zh
    est_tok = int(zh * 0.65 + en_chars * 0.27)
    rows.append((guess, len(names), chars, est_tok, k, names))

rows.sort(key=lambda x: -x[3])
print('%-24s %5s %8s %8s  %s' % ('服务', '工具数', '字符', '≈token', 'hash'))
print('-' * 90)
tot_c = tot_t = tot_n = 0
for g, n, c, t, k, names in rows:
    tot_c += c; tot_t += t; tot_n += n
    print('%-24s %5d %8d %8d  %s' % (g[:24], n, c, t, k[:12]))
print('-' * 90)
print('%-24s %5d %8d %8d' % ('合计', tot_n, tot_c, tot_t))
print()
print('=' * 90)
print('各服务工具名清单')
print('=' * 90)
for g, n, c, t, k, names in rows:
    print('\n### %s  (%d 个工具, ≈%d token)' % (g, n, t))
    for i in range(0, len(names), 6):
        print('   ', ', '.join(names[i:i + 6]))
