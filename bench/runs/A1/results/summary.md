# 统计汇总

## 1. sales.csv 统计

| 指标 | 数值 |
|---|---|
| 数据行数（不含表头） | 6 |
| 订单状态分布 | paid: 4, refunded: 1, pending: 1 |
| 总金额（人民币元） | 680.00 |
| paid 金额 | 550.00 |
| refunded 金额 | 80.00 |
| pending 金额 | 50.00 |
| 去重订单数（order_id） | 5 |

> 说明：A003 出现两次（均为 paid），故去重后为 5 个订单。

## 2. logs/run.log 统计

| 指标 | 数值 |
|---|---|
| INFO 行数 | 998 |
| ERROR 行数 | 2 |
| 总行数 | 1000 |

错误明细：
- 第 137 行：`ERROR E137: missing config`
- 第 811 行：`ERROR E811: timeout`

## 3. 实际生成文件路径

- `results/summary.md`（本文件）
