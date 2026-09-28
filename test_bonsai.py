# -*- coding: utf-8 -*-
"""Bonsai 27B 服务综合测试：多轮稳定性 / 长上下文 / 思考模式 / 工具调用"""
import json
import os
import time
import urllib.request

os.environ['no_proxy'] = '127.0.0.1'
os.environ['NO_PROXY'] = '127.0.0.1'
URL = 'http://127.0.0.1:8080/v1/chat/completions'


def call(messages, **kw):
    payload = {'model': 'bonsai', 'messages': messages}
    payload.update(kw)
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
    )
    t0 = time.time()
    resp = urllib.request.urlopen(req, timeout=300)
    d = json.loads(resp.read())
    dt = time.time() - t0
    msg = d['choices'][0]['message']
    usage = d.get('usage', {})
    return msg, usage, dt, d['choices'][0].get('finish_reason')


print('=' * 60)
print('测试 1: 多轮对话记忆稳定性')
print('=' * 60)
hist = [{'role': 'user', 'content': '我叫张三，今年25岁，是一名软件工程师，住在杭州。请记住。'}]
m, u, dt, fr = call(hist, max_tokens=150, temperature=0.7)
print('[R1]', m.get('content', '')[:300])
hist.append({'role': 'assistant', 'content': m.get('content', '')})

hist.append({'role': 'user', 'content': '我叫什么名字？多大？做什么工作？'})
m, u, dt, fr = call(hist, max_tokens=200, temperature=0.7)
print('[R2 memory]', m.get('content', '')[:400])
hist.append({'role': 'assistant', 'content': m.get('content', '')})

hist.append({'role': 'user', 'content': '以 JSON 格式输出我的全部信息。'})
m, u, dt, fr = call(hist, max_tokens=250, temperature=0.5)
print('[R3 json]', m.get('content', '')[:500])
print('  usage:', u, 'finish:', fr)

print()
print('=' * 60)
print('测试 2: 长上下文检索 (~3K tokens)')
print('=' * 60)
lines = []
for i in range(300):
    lines.append('第%d行：日志数据编号%d，数值%d。' % (i + 1, i + 1, i * 13 + 7))
lines.insert(150, '【重要】密码是 SkyDragon2026，用户ID 是 88493。')
lines.insert(80, '【关键】项目截止日期是 2026年10月15日。')
lines.insert(260, '【隐藏】服务器地址是 192.168.88.100，端口 9527。')
context = '\n'.join(lines)
task = context + '\n\n请精确回答：1)密码？2)用户ID？3)项目截止日期？4)服务器地址和端口？'
m, u, dt, fr = call(
    [{'role': 'system', 'content': '你是精确的信息提取助手，只依据给定文本回答。'},
     {'role': 'user', 'content': task}],
    max_tokens=300, temperature=0.2,
)
print('Response:', m.get('content', '')[:800])
print('  usage:', u, 'finish:', fr, '耗时: %.1fs' % dt)

print()
print('=' * 60)
print('测试 3: 思考模式 (enable_thinking=true)')
print('=' * 60)
m, u, dt, fr = call(
    [{'role': 'user', 'content': '一个农场有鸡和兔子共35只，脚共94只。鸡兔各几只？请逐步思考。'}],
    max_tokens=800, temperature=0.6,
    chat_template_kwargs={'enable_thinking': True},
)
content = m.get('content', '')
print('Response (前600字):', content[:600])
print('  reasoning字段:', repr(m.get('reasoning_content'))[:200])
print('  usage:', u, 'finish:', fr)

print()
print('=' * 60)
print('测试 4: 工具调用 (function calling)')
print('=' * 60)
tools = [{
    'type': 'function',
    'function': {
        'name': 'get_weather',
        'description': '获取指定城市的实时天气',
        'parameters': {
            'type': 'object',
            'properties': {'city': {'type': 'string', 'description': '城市名'}},
            'required': ['city'],
        },
    },
}]
m, u, dt, fr = call(
    [{'role': 'user', 'content': '北京和上海今天天气怎么样？'}],
    max_tokens=300, temperature=0.7, tools=tools,
)
print('content:', (m.get('content') or '')[:300])
print('tool_calls:', json.dumps(m.get('tool_calls', []), indent=2, ensure_ascii=False))
print('  usage:', u, 'finish:', fr)

print()
print('=' * 60)
print('测试 5: 吞吐量 (单次生成速度)')
print('=' * 60)
m, u, dt, fr = call(
    [{'role': 'user', 'content': '写一段 300 字左右的散文，主题是秋天。'}],
    max_tokens=500, temperature=0.8,
)
ct = u.get('completion_tokens', 0)
print('生成 %d tokens / %.1fs = %.2f tok/s' % (ct, dt, ct / dt if dt else 0))
print('usage:', u)
