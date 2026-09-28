# -*- coding: utf-8 -*-
"""快速性能探针"""
import json
import os
import subprocess
import sys
import time
import urllib.request

os.environ['no_proxy'] = '127.0.0.1'
os.environ['NO_PROXY'] = '127.0.0.1'
N = int(sys.argv[1]) if len(sys.argv) > 1 else 64


def vram():
    try:
        return subprocess.check_output(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total',
             '--format=csv,noheader,nounits'], timeout=5).decode().strip()
    except Exception:
        return '?'


payload = {'model': 'bonsai-27b',
           'messages': [{'role': 'user', 'content': '用一句话说明什么是熵。'}],
           'max_tokens': N, 'temperature': 0.7, 'cache_prompt': False}
req = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',
                             data=json.dumps(payload).encode(),
                             headers={'Content-Type': 'application/json'})
t0 = time.time()
d = json.loads(urllib.request.urlopen(req, timeout=900).read())
dt = time.time() - t0
tm = d.get('timings', {})
u = d.get('usage', {})
print('耗时 %.1fs | prefill %.1f t/s (%s tok) | decode %.2f t/s (%s tok) | VRAM %s' % (
    dt, tm.get('prompt_per_second', 0), tm.get('prompt_n'),
    tm.get('predicted_per_second', 0), tm.get('predicted_n'), vram()))
print('usage:', u)
