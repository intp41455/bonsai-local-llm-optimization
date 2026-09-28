# -*- coding: utf-8 -*-
"""解剖抓包：请求结构 + system 消息形态"""
import json, glob, os, sys
sys.stdout.reconfigure(encoding='utf-8')

cap = r'D:\Bonsai-demo\capture'
files = sorted(glob.glob(os.path.join(cap, 'req_*.json')))

for f in files:
    raw = open(f, 'rb').read()
    name = os.path.basename(f)
    print('=' * 78)
    print('%s   %d bytes' % (name, len(raw)))
    try:
        d = json.loads(raw.decode('utf-8'))
    except Exception as e:
        print('  [非 JSON]', e)
        print('  头部:', raw[:200])
        continue

    if not isinstance(d, dict):
        print('  顶层类型:', type(d).__name__)
        continue

    print('  顶层键:', list(d.keys()))
    msgs = d.get('messages')
    if not isinstance(msgs, list):
        print('  (无 messages)')
        continue

    print('  messages: %d 条' % len(msgs))
    for i, m in enumerate(msgs):
        if not isinstance(m, dict):
            print('   [%2d] %s' % (i, type(m).__name__))
            continue
        role = m.get('role')
        c = m.get('content')
        if isinstance(c, str):
            ln = len(c)
            tail = c[-90:].replace('\n', '\\n')
            head = c[:70].replace('\n', '\\n')
            print('   [%2d] %-9s len=%-7d' % (i, role, ln))
            print('         head: %s' % head)
            print('         tail: %s' % tail)
        elif isinstance(c, list):
            print('   [%2d] %-9s parts=%d' % (i, role, len(c)))
            for j, p in enumerate(c[:6]):
                t = p.get('type') if isinstance(p, dict) else '?'
                txt = json.dumps(p, ensure_ascii=False)[:150]
                print('          part[%d] %s :: %s' % (j, t, txt))
        else:
            print('   [%2d] %-9s content=%s' % (i, role, type(c).__name__))
        # tool_calls
        if m.get('tool_calls'):
            print('         tool_calls=%d' % len(m['tool_calls']))

    # 其他关键字段
    t = d.get('tools')
    if isinstance(t, list):
        print('  tools: %d 个' % len(t))
        raw_tj = json.dumps(t, ensure_ascii=False)
        print('  tools 序列化长度: %d 字符' % len(raw_tj))
    for k in ('model', 'max_tokens', 'stream', 'temperature', 'chat_template_kwargs'):
        if k in d:
            print('  %s = %s' % (k, json.dumps(d[k], ensure_ascii=False)[:160]))
