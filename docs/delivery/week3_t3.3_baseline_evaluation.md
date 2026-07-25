# Week 3 T3.3 平衡 Gold 与冻结基线评估

- 日期：2026-07-25
- Gold 状态：**已人工审核并冻结**
- 评估性质：小样本初评

## Gold 组成

- evidence unit：27
- 报告：5
- 正样本：15（10 chart、5 table）
- 负样本：12

第二轮补充审核接受 7 条、拒绝 1 条。拒绝项 `week3_030` 的“市场份额”列混入了其他指标，
定稿为 `reject.mixed_metric_or_unit`。

负样本精简采用确定性规则：首先保留全部冻结基线误报，再优先增加新的拒绝原因、报告和来源类型。
最终拒绝原因分布为：

- mixed metric/unit：6
- single number：2
- administrative numbers only：2
- non-composition percentages：1
- single-point signal：1

## 冻结基线指标

| 指标 | 分子/分母 | 结果 | MVP 最低门槛 |
|---|---:|---:|---:|
| Candidate Precision | 11/18 | 61.11% | 70% |
| Candidate Recall | 11/15 | 73.33% | 80% |
| Candidate F1 | — | 66.67% | — |
| Chart type accuracy | 11/11 | 100% | — |
| 完整对象准确率 | 11/15 | 73.33% | 70% |
| 数值单元格 Precision | 136/168 | 80.95% | — |
| 数值单元格 Recall | 136/174 | 78.16% | — |
| 数值单元格 Exact Match | 136/206 | 66.02% | 90% |
| 正确拒绝率 | 5/12 | 41.67% | — |
| 拒绝原因准确率 | 4/12 | 33.33% | — |
| Schema 通过率 | 18/18 | 100% | 100% |
| sources 覆盖率 | 18/18 | 100% | 100% |
| 编造数值 | 0 | 0 | 0 |

基线有 7 个误报和 4 个漏报。漏报为补充批次中 Locator 未发现的完整表格：
`week3_028`、`week3_032`、`week3_034`、`week3_035`。数值 FP 32 个全部来自误报候选中的
可追溯真实数值，不是编造数值。

## 结论

平衡集揭示 Candidate Locator 同时存在 Precision 和 Recall 问题：

- 对同一段落中的多个异构数字过度建立比较关系；
- 把带年份描述但只有一个有效数值的段落误判为趋势；
- 把 CAGR 摘要、风险描述等缺少完整序列的段落误判为图表候选。
- 对部分完整表格缺少主动发现能力。

完整对象准确率、Schema、sources 和零编造数值达到门槛；Candidate Precision、Recall 和数值
Exact Match 尚未达到门槛。后续规则调整应围绕通用约束和 complete table 召回，不针对具体
样本文本写特例。

## 可复现文件

- `data/evaluation/visualization/week3_gold.jsonl`
- `data/evaluation/visualization/week3_baseline_predictions.jsonl`
- `data/evaluation/visualization/week3_baseline_report.json`
- `data/evaluation/visualization/week3_initial_gold.jsonl`
- `data/evaluation/visualization/week3_initial_baseline_predictions.jsonl`
- `data/evaluation/visualization/week3_positive_supplement_gold.jsonl`
- `tools/merge_visualization_gold.py`
