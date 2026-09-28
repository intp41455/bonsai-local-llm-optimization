# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\intpj\.workbuddy\settings.json'
t = open(p, encoding='utf-8').read()
i = t.find('"skillOverrides"')
print('--- skillOverrides 键偏移 %d ---' % i)
print(repr(t[i:i + 300]))
k = t.find('{', i)
depth = 0
end = k
while end < len(t):
    if t[end] == '{':
        depth += 1
    elif t[end] == '}':
        depth -= 1
        if depth == 0:
            break
    end += 1
print()
print('object span: %d .. %d' % (k, end))
print('结尾片段:', repr(t[end - 140:end + 40]))
print()
print('文件总长:', len(t))
print('前 40 字符:', repr(t[:40]))
# 检查换行符
print('CRLF 数:', t.count('\r\n'), ' LF 数:', t.count('\n'))
