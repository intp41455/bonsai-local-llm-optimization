# -*- coding: utf-8 -*-
"""对照实验 4：长上下文 x offload 层数的平衡点"""
import json
import os
import subprocess
import time
import urllib.request

BASE = r'D:\Bonsai-demo'
BIN = os.path.join(BASE, 'bin', 'cuda')
MODEL = os.path.join(BASE, 'models', 'bonsai2-gguf', '27B', 'Ternary-Bonsai-2-27B-PQ2_0.gguf')
MMPROJ = os.path.join(BASE, 'models', 'bonsai2-gguf', '27B', 'Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf')
os.environ['no_proxy'] = '127.0.0.1'
os.environ['NO_PROXY'] = '127.0.0.1'
KV4 = ['--cache-type-k', 'q4_0', '--cache-type-v', 'q4_0']


def vram():
    try:
        return subprocess.check_output(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            timeout=5).decode().strip()
    except Exception:
        return '?'


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
    payload = {'model': 'bonsai',
               'messages': [{'role': 'user', 'content': '用一句话说明什么是熵。'}],
               'max_tokens': max_tokens, 'temperature': 0.7, 'cache_prompt': False}
    req = urllib.request.Request(
        'http://127.0.0.1:%d/v1/chat/completions' % port,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=900).read())
    dt = time.time() - t0
    tm = d.get('timings', {})
    return {'wall_s': round(dt, 1),
            'pp_tps': round(tm.get('prompt_per_second', 0), 2),
            'tg_tps': round(tm.get('predicted_per_second', 0), 2)}


def run(name, ngl, ctx):
    port = 8080
    env = dict(os.environ)
    env['PATH'] = BIN + os.pathsep + env['PATH']
    args = [os.path.join(BIN, 'llama-server.exe'),
            '-m', MODEL, '--host', '127.0.0.1', '--port', str(port),
            '--jinja', '--temp', '1.0', '--top-p', '0.95', '--top-k', '20', '--min-p', '0.05',
            '-ngl', str(ngl), '-fa', 'on', '-c', str(ctx), '-np', '1'] + KV4 + \
           ['--mmproj', MMPROJ, '--no-mmproj-offload']
    log = open(os.path.join(BASE, 'bench_%s.log' % name), 'w', encoding='utf-8')
    print('=== %s : ngl=%d ctx=%d ===' % (name, ngl, ctx), flush=True)
    p = subprocess.Popen(args, cwd=BASE, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        if not wait_health(port):
            print('  [FAIL] 未就绪', flush=True)
            return None
        time.sleep(3)
        v = vram()
        r = probe(port)
        r['vram_MiB'] = v
        r['headroom_MiB'] = 8151 - int(v)
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


CONFIGS = {
    'F_ngl56_ctx16k': (56, 16384),
    'G_ngl52_ctx32k': (52, 32768),
    'H_ngl56_ctx24k': (56, 24576),
}
results = {}
for name, (ngl, ctx) in CONFIGS.items():
    try:
        results[name] = run(name, ngl, ctx)
    except Exception as e:
        print('  [ERR]', e, flush=True)
        results[name] = {'error': str(e)}

print()
print('=' * 72)
print('%-18s %-10s %-10s %-12s %s' % ('config', 'pp t/s', 'tg t/s', 'vram MiB', 'headroom'))
print('=' * 72)
for k, v in results.items():
    if v and 'tg_tps' in v:
        print('%-18s %-10s %-10s %-12s %s' % (k, v['pp_tps'], v['tg_tps'],
                                              v['vram_MiB'], v['headroom_MiB']))
    else:
        print('%-18s %s' % (k, v))
