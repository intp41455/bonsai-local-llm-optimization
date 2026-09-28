# 统计汇总

## 1. sales.csv 统计

| 指标 | 数值 |
|---|---|
| 数据行数（含重复） | 6 |
| 唯一订单数（去重 order_id） | 5 |
| 重复订单 | A003（出现 2 次） |
| 状态分布 | paid=4, refunded=1, pending=1 |
| 总金额（含重复行） | 680 |
| 去重后总金额 | 480 |
| 已支付（paid）订单数（去重） | 3 |
| 已支付（paid）金额（去重） | 350 |

> 去重后已支付统计：3 笔订单，合计 350，与 MANIFEST.json 中
> `task11_preset_sales_json`（count=3, amount=350）一致。

## 2. logs/run.log 统计

| 指标 | 数值 |
|---|---|
| 总行数 | 1000 |
| INFO 行数 | 998 |
| ERROR 行数 | 2 |
| 处理行号范围 | 1 – 1000 |
| 有效 row 记录数 | 998 |
| 缺失行号（即错误行） | 137, 811 |

**错误明细：**

| 行号 | 错误 |
|---|---|
| 137 | ERROR E137: missing config |
| 811 | ERROR E811: timeout |

## 3. 实际生成文件路径

- `results/summary.md`（本文件）
