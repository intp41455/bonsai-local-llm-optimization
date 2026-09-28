# -*- coding: utf-8 -*-
"""Bonsai 2 27B（推荐档）功能验收：多轮稳定性 / 长上下文 / 思考 / 工具调用 / 吞吐"""
import json
import os
import time
import urllib.request

os.environ['no_proxy'] = '127.0.0.1'
os.environ['NO_PROXY'] = '127.0.0.1'
URL = 'http://127.0.0.1:8080/v1/chat/completions'


def call(messages, **kw):
    payload = {'model': 'bonsai-27b', 'messages': messages}
    payload.update(kw)
    req = urllib.request.Request(URL, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    dt = time.time() - t0
    ch = d['choices'][0]
    return ch['message'], d.get('usage', {}), d.get('timings', {}), dt, ch.get('finish_reason')


def show(tag, m, u, tm, dt, fr, limit=500):
    body = m.get('content') or ''
    rc = m.get('reasoning_content') or ''
    print('[%s] 耗时 %.1fs | pp %.1f t/s | tg %.1f t/s | finish=%s' % (
        tag, dt, tm.get('prompt_per_second', 0), tm.get('predicted_per_second', 0), fr))
    if rc:
        print('   (思考 %d 字) %s' % (len(rc), rc[:180].replace('\n', ' ')))
    print('   ' + body[:limit].replace('\n', '\n   '))
    print('   usage:', u)
    print()


print('#' * 66)
print('T1  多轮对话稳定性（记忆 + 格式跟随）')
print('#' * 66)
hist = [{'role': 'user', 'content': '我叫张三，25 岁，软件工程师，住杭州，养了一只叫年糕的猫。'}]
m, u, tm, dt, fr = call(hist, max_tokens=150)
show('R1', m, u, tm, dt, fr, 200)
hist.append({'role': 'assistant', 'content': m.get('content') or ''})

hist.append({'role': 'user', 'content': '我叫什么？多大？住哪？猫叫什么名字？'})
m, u, tm, dt, fr = call(hist, max_tokens=250)
show('R2 记忆', m, u, tm, dt, fr, 300)
hist.append({'role': 'assistant', 'content': m.get('content') or ''})

hist.append({'role': 'user', 'content': '把关于我的所有信息整理成 JSON，键用英文。'})
m, u, tm, dt, fr = call(hist, max_tokens=300, temperature=0.5)
show('R3 JSON', m, u, tm, dt, fr, 400)

print('#' * 66)
print('T2  长上下文检索（约 3K tokens）')
print('#' * 66)
lines = ['第%d行：日志编号%d，数值%d。' % (i + 1, i + 1, i * 13 + 7) for i in range(300)]
lines.insert(150, '【重要】密码是 SkyDragon2026，用户ID 是 88493。')
lines.insert(80, '【关键】项目截止日期是 2026年10月15日。')
lines.insert(260, '【隐藏】服务器 192.168.88.100，端口 9527。')
ctx = '\n'.join(lines)
m, u, tm, dt, fr = call(
    [{'role': 'system', 'content': '你是精确的信息提取助手，只依据给定文本回答，不要脑补。'},
     {'role': 'user', 'content': ctx + '\n\n请回答：1)密码？2)用户ID？3)项目截止日期？4)服务器地址和端口？'}],
    max_tokens=400, temperature=0.2)
show('T2-3K', m, u, tm, dt, fr, 700)

print('#' * 66)
print('T3  超长上下文检索（约 8K tokens，接近 16K 上限的一半）')
print('#' * 66)
lines2 = ['记录%d：传感器读数 %d，状态正常。' % (i + 1, (i * 37) % 999) for i in range(800)]
lines2.insert(400, '【核心】退货率异常的根本原因是 3 号仓库冷链温度超标，阈值 8℃。')
lines2.insert(120, '【备注】责任人 李工，工号 A2291。')
lines2.insert(700, '【结论】整改期限 2026年11月30日。')
ctx2 = '\n'.join(lines2)
m, u, tm, dt, fr = call(
    [{'role': 'system', 'content': '你是精确的信息提取助手，只依据给定文本回答。'},
     {'role': 'user', 'content': ctx2 + '\n\n请回答：1)退货率异常的根本原因？2)温度阈值？3)责任人姓名和工号？4)整改期限？'}],
    max_tokens=400, temperature=0.2)
show('T3-8K', m, u, tm, dt, fr, 700)

print('#' * 66)
print('T4  思考模式（显式开启，观察 reasoning_content）')
print('#' * 66)
m, u, tm, dt, fr = call(
    [{'role': 'user', 'content': '一个农场有鸡和兔共 35 只，脚共 94 只。鸡兔各几只？'}],
    max_tokens=1200, thinking_budget_tokens=1024)
show('T4 思考', m, u, tm, dt, fr, 400)

print('#' * 66)
print('T5  工具调用（native function calling）')
print('#' * 66)
tools = [{'type': 'function', 'function': {
    'name': 'get_weather', 'description': '获取指定城市的实时天气',
    'parameters': {'type': 'object', 'properties': {'city': {'type': 'string', 'description': '城市名'}},
                   'required': ['city']}}}]
m, u, tm, dt, fr = call([{'role': 'user', 'content': '北京和上海今天天气怎么样？'}],
                        max_tokens=400, tools=tools)
print('[T5] 耗时 %.1fs | finish=%s' % (dt, fr))
print('   content:', (m.get('content') or '')[:300])
print('   tool_calls:', json.dumps(m.get('tool_calls', []), ensure_ascii=False, indent=2))
print()

print('#' * 66)
print('T6  吞吐（连续生成 300 tokens）')
print('#' * 66)
m, u, tm, dt, fr = call([{'role': 'user', 'content': '写一篇约 400 字的散文，主题是秋天。'}],
                        max_tokens=500, temperature=0.8)
ct = u.get('completion_tokens', 0)
print('生成 %d tokens / %.1fs = %.2f tok/s（首字延迟 pp %.1f t/s）' % (
    ct, dt, ct / dt if dt else 0, tm.get('prompt_per_second', 0)))
print('usage:', u)
