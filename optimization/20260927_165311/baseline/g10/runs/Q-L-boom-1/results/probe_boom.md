# probe/boom.py 运行结果

## 是否成功
**失败**（exit code = 1）

## 错误原文（stderr）
```
Traceback (most recent call last):
  File "D:\Bonsai-demo\optimization\20260927_165311\baseline\g10\runs\Q-L-boom-1\probe\boom.py", line 1, in <module>
    raise RuntimeError("E_PARSE: config field 'amount' has the wrong shape")
RuntimeError: E_PARSE: config field 'amount' has the wrong shape
```

## 说明
脚本仅包含一行 `raise RuntimeError("E_PARSE: config field 'amount' has the wrong shape")`，因此必然抛出 `RuntimeError` 并退出，exit code 为 1。
