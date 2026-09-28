# probe/boom.py 运行结果

## 是否成功
**失败**（exit code = 1）

## 错误原文（stderr）
```
Traceback (most recent call last):
  File "D:\Bonsai-demo\optimization\20260927_165311\baseline\g10\runs\P-L-boom-1\probe\boom.py", line 1, in <module>
    raise RuntimeError("E_PARSE: config field 'amount' has the wrong shape")
RuntimeError: E_PARSE: config field 'amount' has the wrong shape
```

## 说明
脚本仅有一行，主动抛出 `RuntimeError`，报错信息为：
`E_PARSE: config field 'amount' has the wrong shape`
