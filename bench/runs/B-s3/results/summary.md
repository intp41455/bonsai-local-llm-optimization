# 统计汇总

## 1. sales.csv 统计

| 指标 | 数值 |
|---|---|
| 数据行数（不含表头） | 6 |
| 唯一订单数 | 5（A003 出现 2 次） |
| 总金额 | 680 |
| paid 订单数 / 金额 | 4 / 550 |
| refunded 订单数 / 金额 | 1 / 80 |
| pending 订单数 / 金额 | 1 / 50 |

明细：

| order_id | amount | status |
|---|---|---|
| A001 | 120 | paid |
| A002 | 80 | refunded |
| A003 | 200 | paid |
| A003 | 200 | paid |
| A004 | 50 | pending |
| A005 | 30 | paid |

## 2. logs/run.log 统计

| 指标 | 数值 |
|---|---|
| 总行数 | 1000 |
| INFO 行数 | 998 |
| ERROR 行数 | 2 |

错误明细：

| 行号 | 内容 |
|---|---|
| 137 | ERROR E137: missing config |
| 811 | ERROR E811: timeout |

## 3. 实际生成文件路径

- `results/summary.md`（本文件）
- `count_stats.py`（统计脚本）
- `check_log.py`（日志校验脚本）
