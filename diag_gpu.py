# -*- coding: utf-8 -*-
"""诊断：推理时 GPU 利用率采样 —— 判断到底 GPU 在干活还是 CPU 在扛"""
import json
import os
import subprocess
import threading
import time
import urllib.request

os.environ['no_proxy'] = '127.0.0.1'
URL = 'http://127.0.0.1:8080/v1/chat/completions'

samples = []
stop = False


def sample():
    while not stop:
        try:
            out = subprocess.check_output(
                ['nvidia-smi',
                 '--query-gpu=utilization.gpu,utilization.memory,power.draw',
                 '--format=csv,noheader,nounits'],
                timeout=5).decode().strip()
            samples.append(out)
        except Exception as e:
            samples.append('ERR ' + str(e))
        time.sleep(1)


t = threading.Thread(target=sample, daemon=True)
t.start()

payload = {
    'model': 'bonsai',
    'messages': [{'role': 'user', 'content': '请详细写一篇 300 字的关于量子计算的科普短文。'}],
    'max_tokens': 200,
    'temperature': 0.7,
}
req = urllib.request.Request(URL, data=json.dumps(payload).encode(),
                            headers={'Content-Type': 'application/json'})
print('>>> 发送请求，开始采样 GPU 利用率...')
t0 = time.time()
resp = urllib.request.urlopen(req, timeout=600)
d = json.loads(resp.read())
dt = time.time() - t0
stop = True
time.sleep(1.2)

u = d.get('usage', {})
tm = d.get('timings', {})
print('>>> 完成，耗时 %.1fs' % dt)
print('usage:', u)
if tm:
    print('timings: pp=%.1f t/s  tg=%.1f t/s  prompt_n=%s  predicted_n=%s' % (
        tm.get('prompt_per_second', 0), tm.get('predicted_per_second', 0),
        tm.get('prompt_n'), tm.get('predicted_n')))
print()
print('=== GPU 利用率采样 (util.gpu%, util.mem%, power W) ===')
for s in samples:
    print('  ', s)
utils = []
for s in samples:
    p = s.split(',')
    if len(p) >= 1:
        try:
            utils.append(float(p[0].strip()))
        except ValueError:
            pass
if utils:
    print()
    print('平均 GPU 利用率: %.1f%%   峰值: %.1f%%   最小: %.1f%%' % (
        sum(utils) / len(utils), max(utils), min(utils)))
