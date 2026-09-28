# -*- coding: utf-8 -*-
"""决定性实验：重放抓包序列，测冷/热 prefill，并验证"旁路调用冲掉缓存"假说"""
import json, os, sys, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'http://127.0.0.1:8081'
cap = r'D:\Bonsai-demo\capture'


def send(body, max_tokens=8):
    req = dict(body)
    req['stream'] = False
    req.pop('stream_options', None)
    req['max_tokens'] = max_tokens
    data = json.dumps(req, ensure_ascii=False).encode('utf-8')
    r = urllib.request.Request(BASE + '/v1/chat/completions', data=data,
                               headers={'Content-Type': 'application/json'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(r, timeout=1800) as resp:
            d = json.loads(resp.read().decode('utf-8'))
        dt = time.time() - t0
        tm = d.get('timings') or {}
        return {
            'wall': dt,
            'prompt_n': tm.get('prompt_n'),
            'prompt_ms': tm.get('prompt_ms'),
            'cache_n': tm.get('cache_n'),
            'prefill_tps': tm.get('prompt_per_second'),
            'decode_n': tm.get('predicted_n'),
            'decode_tps': tm.get('predicted_per_second'),
            'text': (d.get('choices', [{}])[0].get('message', {}) or {}).get('content', '')[:60],
        }
    except Exception as e:
        return {'wall': time.time() - t0, 'error': str(e)[:200]}


def load(name):
    return json.load(open(os.path.join(cap, name), encoding='utf-8'))


R4 = load('req_004_052534.json')
R5 = load('req_005_052847.json')
R6 = load('req_006_053121.json')

print('=' * 92)
print('%-34s %8s %9s %11s %10s %10s' % ('阶段', '耗时s', 'prompt_n', 'prefill_ms', 'prefill_t/s', 'decode_t/s'))
print('=' * 92)

results = []


def run(label, body, mt=8):
    r = send(body, mt)
    if 'error' in r:
        print('%-34s %8.1f  ERROR %s' % (label, r['wall'], r['error']))
    else:
        print('%-34s %8.1f %9s %11.0f %10.1f %10.2f   | %s' % (
            label, r['wall'],
            r.get('prompt_n'), r.get('prompt_ms') or 0,
            r.get('prefill_tps') or 0, r.get('decode_tps') or 0,
            (r.get('text') or '').replace('\n', ' ')))
    results.append((label, r))
    sys.stdout.flush() if hasattr(sys.stdout, 'flush') else None


# A. 冷启动：全新进程后的第一次
run('A 冷启动 req_004', R4)
# B/C. 追加型：应当几乎全部命中
run('B 追加 req_005', R5)
run('C 追加 req_006', R6)

# D. 旁路调用（模拟摘要/标题生成这类完全不同的 prompt）
run('D 旁路小请求（冲缓存）', {
    'model': 'bonsai-2-27b',
    'messages': [{'role': 'system', 'content': 'You are a helpful AI assistant tasked with summarizing conversations.'},
                 {'role': 'user', 'content': '把下面这段压成一句话：今天天气不错，我们去了公园。'}],
}, mt=12)

# E. 旁路之后再发真实请求 —— 假说成立的话，这里又会冷启动
run('E 旁路后再发 req_006', R6)

print('=' * 92)
print()
print('【判读】')
for label, r in results:
    if 'error' in r:
        continue
    pn = r.get('prompt_n') or 0
    print('  %-30s prompt_n=%-7s  复用率≈%.1f%%' % (
        label, pn,
        (1 - pn / 57885.0) * 100 if pn else 100.0))
