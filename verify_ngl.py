# -*- coding: utf-8 -*-
"""验证：完整推荐参数下，不同 ngl 的速度/显存（含偏置 + 思考 medium）"""
import json
import os
import subprocess
import time
import urllib.request

BASE = r'D:\Bonsai-demo'
BIN = os.path.join(BASE, 'bin', 'cuda')
MODEL = os.path.join(BASE, 'models', 'bonsai2-gguf', '27B', 'Ternary-Bonsai-2-27B-PQ2_0.gguf')
MMPROJ = os.path.join(BASE, 'models', 'bonsai2-gguf', '27B', 'Ternary-Bonsai-2-27B-mmproj-Q8_0.gguf')
BIAS = os.path.join(BASE, 'models', 'bonsai2-gguf', '27B', 'Bonsai-2-27B-kv-bias.gguf')
os.environ['no_proxy'] = '127.0.0.1'
os.environ['NO_PROXY'] = '127.0.0.1'


def vram():
    try:
        return int(subprocess.check_output(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            timeout=5).decode().strip())
    except Exception:
        return -1


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


def probe(port, max_tokens=96):
    payload = {'model': 'bonsai-27b',
               'messages': [{'role': 'user', 'content': '用一句话说明什么是熵。'}],
               'max_tokens': max_tokens, 'temperature': 0.7, 'cache_prompt': False}
    req = urllib.request.Request('http://127.0.0.1:%d/v1/chat/completions' % port,
                                 data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.time()
    d = json.loads(urllib.request.urlopen(req, timeout=900).read())
    dt = time.time() - t0
    tm = d.get('timings', {})
    return {'wall_s': round(dt, 1),
            'pp': round(tm.get('prompt_per_second', 0), 1),
            'tg': round(tm.get('predicted_per_second', 0), 2)}


def run(ngl, ctx):
    port = 8080
    env = dict(os.environ)
    env['PATH'] = BIN + os.pathsep + env['PATH']
    args = [os.path.join(BIN, 'llama-server.exe'), '-m', MODEL,
            '--host', '127.0.0.1', '--port', str(port), '-a', 'bonsai-27b',
            '-ngl', str(ngl), '-fa', 'on', '-c', str(ctx), '-np', '1',
            '--temp', '1.0', '--top-p', '0.95', '--top-k', '20', '--min-p', '0.05',
            '-rea', 'on', '--reasoning-effort', 'medium',
            '--reasoning-format', 'deepseek', '--jinja',
            '--mmproj', MMPROJ, '--no-mmproj-offload',
            '-ctk', 'q4_0', '-ctv', 'q4_0', '--kv-mean-center', BIAS]
    log = open(os.path.join(BASE, 'verify_ngl%d.log' % ngl), 'w', encoding='utf-8')
    print('=== ngl=%d ctx=%d ===' % (ngl, ctx), flush=True)
    p = subprocess.Popen(args, cwd=BASE, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        if not wait_health(port):
            print('  [FAIL] 未就绪', flush=True)
            return None
        time.sleep(3)
        v = vram()
        r = probe(port)
        r['vram'] = v
        r['headroom'] = 8151 - v
        print('  ', json.dumps(r, ensure_ascii=False), flush=True)
        return r
    finally:
        p.terminate()
        try:
            p.wait(timeout=20)
        except Exception:
            p.kill()
        log.close()
        time.sleep(5)


res = {}
for ngl in [52, 56]:
    try:
        res[ngl] = run(ngl, 16384)
    except Exception as e:
        print('  [ERR]', e, flush=True)
        res[ngl] = {'error': str(e)}

print()
print('%-6s %-8s %-8s %-10s %s' % ('ngl', 'pp', 'tg', 'vram', 'headroom'))
for k, v in res.items():
    if v and 'tg' in v:
        print('%-6s %-8s %-8s %-10s %s' % (k, v['pp'], v['tg'], v['vram'], v['headroom']))
    else:
        print('%-6s %s' % (k, v))
