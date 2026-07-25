# Week 3 T3.3 正样本补充审核

- 状态：**人工审核完成，已合并**
- 日期：2026-07-25
- 批次：`week3_028`–`week3_035`

## 目的

首轮人工 Gold 只有 8 个正样本。补充批次从未使用的 complete table 中独立选择 8 条，
用于把最终正样本数量提高到计划要求的 15 条左右，同时测量 Candidate Locator 的漏召回。

## 来源与分布

- `001309_2025-10-28`：3 条；
- `002444_2025-09-21`：3 条；
- `002821_2025-09-11`：2 条；
- 全部为 complete table；
- 建议包含 table、trend line 和 composition pie。

其中前两份报告没有进入首轮 Gold，扩大了报告覆盖。补充表格由确定性 table scan 选择，
不是只从 Locator 已命中的候选中抽样。

## 冻结文件

- `week3_positive_supplement_draft.jsonl`
- `week3_positive_supplement_review.md`
- `week3_positive_supplement_baseline_predictions.jsonl`

审核前的 Locator 预测已冻结：8 条中当前系统命中 3 条、漏掉 5 条。人工审核完成前不得重新生成
baseline predictions。

## 人工审核结果

- 接受：7 条；
- 拒绝：1 条（`week3_030`）；
- 拒绝原因：市场份额列混入其他口径，映射为
  `reject.mixed_metric_or_unit`。

审核结果已生成 `week3_positive_supplement_gold.jsonl`。冻结的 Locator 预测仍为 3 条命中、
5 条未命中，并已与首轮预测按最终 Gold 的 sample ID 对齐。

## 合并结果

- 最终 Gold：27 条；
- 正样本：15 条；
- 负样本：12 条；
- 报告覆盖：5 份；
- 合并和负样本选择由 `tools/merge_visualization_gold.py` 确定性完成。
