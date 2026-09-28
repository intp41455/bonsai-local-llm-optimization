# -*- coding: utf-8 -*-
"""对照实验：不同启动配置下的 prefill / decode 速度
目的：判断瓶颈是 (a) 显存压力 还是 (b) kernel 效率
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

BASE = r'D:\Bonsai-demo'
BIN = os.path.join(BASE, 'bin', 'cuda')
MODEL = os.path.join(BASE, 'models', 'bonsai2-gguf', '27B', 'Ternary-Bonsai-2-27B-PQ2_0.gguf')
MMPROJ = os.path.join(BASE, 'models', 'bonsai2-gguf', '27B', 'Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf')

os.environ['no_proxy'] = '127.0.0.1'
os.environ['NO_PROXY'] = '127.0.0.1'
os.environ['BONSAI_KV4'] = '0'


def wait_health(port, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = urllib.request.urlopen('http://127.0.0.1:%d/health' % port, timeout=3)
            if json.loads(r.read()).get('status') == 'ok':
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def probe(port, max_tokens=64):
    payload = {
        'model': 'bonsai',
        'messages': [{'role': 'user', 'content': '用一句话说明什么是熵。'}],
        'max_tokens': max_tokens,
        'temperature': 0.7,
        'cache_prompt': False,
    }
    req = urllib.request.Request(
        'http://127.0.0.1:%d/v1/chat/completions' % port,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=900).read())
    dt = time.time() - t0
    tm = d.get('timings', {})
    return {
        'wall_s': round(dt, 1),
        'pp_tps': round(tm.get('prompt_per_second', 0), 2),
        'tg_tps': round(tm.get('predicted_per_second', 0), 2),
        'prompt_n': tm.get('prompt_n'),
        'predicted_n': tm.get('predicted_n'),
    }


CONFIGS = {
    # A: CPU-only —— 决定性对照（GPU 是否真在加速）
    'A_cpu_only': ['-ngl', '0'],
    # B: 瘦身 GPU —— 小 context/单槽/小 batch + f16 KV + 无投影器
    'B_slim_gpu': ['-ngl', '99', '-fa', 'on', '-c', '4096', '-np', '1',
                   '-b', '512', '-ub', '128'],
}


def run(name, extra):
    port = 8080
    env = dict(os.environ)
    env['PATH'] = BIN + os.pathsep + env['PATH']
    args = [os.path.join(BIN, 'llama-server.exe'),
            '-m', MODEL, '--host', '127.0.0.1', '--port', str(port),
            '--jinja', '--temp', '1.0', '--top-p', '0.95', '--top-k', '20',
            '--min-p', '0.05'] + extra
    log = open(os.path.join(BASE, 'bench_%s.log' % name), 'w', encoding='utf-8')
    print('=' * 60)
    print('配置 %s : %s' % (name, ' '.join(extra)))
    print('=' * 60, flush=True)
    p = subprocess.Popen(args, cwd=BASE, env=env,
                         stdout=log, stderr=subprocess.STDOUT)
    try:
        if not wait_health(port):
            print('  [FAIL] 服务未就绪', flush=True)
            return None
        time.sleep(3)
        r = probe(port)
        print('  结果:', json.dumps(r, ensure_ascii=False), flush=True)
        return r
    finally:
        p.terminate()
        try:
            p.wait(timeout=20)
        except Exception:
            p.kill()
        log.close()
        time.sleep(5)


results = {}
for name, extra in CONFIGS.items():
    try:
        results[name] = run(name, extra)
    except Exception as e:
        print('  [ERR]', e, flush=True)
        results[name] = {'error': str(e)}

print()
print('=' * 60)
print('汇总')
print('=' * 60)
for k, v in results.items():
    print('%-14s %s' % (k, json.dumps(v, ensure_ascii=False)))
