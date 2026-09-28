# 统计汇总

## sales.csv
- 数据行数：6
- 唯一订单数：5（A003 重复出现 2 次）
- 状态分布：paid 4、refunded 1、pending 1
- 金额合计：680.0
  - paid：550.0
  - refunded：80.0
  - pending：50.0

## logs/run.log
- 总行数：1000
- INFO：998
- ERROR：2
  - `ERROR E137: missing config`
  - `ERROR E811: timeout`

## 实际生成文件路径
- `results/summary.md`（本文件）
