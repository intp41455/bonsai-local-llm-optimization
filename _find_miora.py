import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')

roots = [
    r'C:\Users\intpj\.workbuddy',
    r'C:\Users\intpj\AppData\Roaming\WorkBuddy',
    r'C:\Users\intpj\.config\opencode',
]
KEY = 'miora'
hits = []
for root in roots:
    if not os.path.isdir(root):
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        # 跳过明显无关的大目录
        dirnames[:] = [d for d in dirnames if d.lower() not in
                       ('binaries', 'blobs', 'clipboard-images', 'node_modules', 'cache')]
        depth = dirpath[len(root):].count(os.sep)
        if depth > 4:
            dirnames[:] = []
            continue
        for fn in filenames:
            if not fn.lower().endswith(('.json', '.jsonc', '.js', '.txt', '.md')):
                continue
            p = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(p) > 20 * 1024 * 1024:
                    continue
                txt = open(p, encoding='utf-8', errors='ignore').read()
            except Exception:
                continue
            low = txt.lower()
            n = low.count(KEY)
            if n:
                hits.append((p, n, len(txt), txt))

hits.sort(key=lambda x: -x[1])
print('=== 含 miora 的文件 ===')
for p, n, sz, _ in hits:
    print('%5d 次  %8d B  %s' % (n, sz, p))
if not hits:
    print('(无)')
print()

# 打印最相关的一份内容片段
for p, n, sz, txt in hits[:3]:
    print('=' * 70)
    print('FILE:', p)
    low = txt.lower()
    start = 0
    for _ in range(3):
        i = low.find(KEY, start)
        if i < 0:
            break
        print('--- 片段 @%d ---' % i)
        print(txt[max(0, i-400):i+400])
        print()
        start = i + 5
