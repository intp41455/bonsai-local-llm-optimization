# 统计汇总

## 1. sales.csv 统计

| 指标 | 数值 |
|---|---|
| 数据行数（不含表头） | 6 |
| 唯一订单数（order_id） | 5（A003 重复出现 2 次） |
| 总金额 | 680.0 |
| paid 订单数 / 金额 | 4 / 550.0 |
| refunded 订单数 / 金额 | 1 / 80.0 |
| pending 订单数 / 金额 | 1 / 50.0 |

明细：
- A001: 120 paid
- A002: 80 refunded
- A003: 200 paid（重复 2 行）
- A004: 50 pending
- A005: 30 paid

## 2. logs/run.log 统计

| 指标 | 数值 |
|---|---|
| 总行数 | 1000 |
| INFO 行数 | 998 |
| ERROR 行数 | 2 |

错误明细：
- `ERROR E137: missing config`
- `ERROR E811: timeout`

## 3. 实际生成文件路径

- `results/summary.md`（本文件）
