# 修复记录

## 任务
修复 `calc.py` 的 `total_paid` 函数：
- 仅汇总 `status == 'paid'` 的行
- 按 `order_id` 去重（同一订单只计一次）
- 保留函数名 `total_paid`

## 修复前
```python
def total_paid(rows):
    return sum(float(r['amount']) for r in rows)
```
问题：未过滤 status，未去重 order_id。

## 修复后
```python
def total_paid(rows):
    seen = set()
    total = 0.0
    for r in rows:
        if r['status'] == 'paid' and r['order_id'] not in seen:
            seen.add(r['order_id'])
            total += float(r['amount'])
    return total
```

## 验证
- `sales.csv` → **350.0**（A001=120 + A003=200 + A005=30；A003 重复行只计一次，A002 refunded / A004 pending 排除）
- 空列表 → 0.0
- 无 paid 行 → 0.0
- 重复 order_id（不同金额）→ 取首次出现
- 同 order_id 混合 status → 仅 paid 计入
- 浮点金额 → 正确累加

所有测试通过。
