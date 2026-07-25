# Week 3 T3.3 预标注与评估工具交付记录

- 状态：**人工审核已完成**
- 日期：2026-07-25
- 当前阶段：27 条 gold 已冻结，首版评估已生成

## 已选来源

- `000333_2025-10-30.md`
- `002544_2025-10-28.md`
- `002821_2025-09-11.md`

三份报告在表格数量、数字密度和业务主题上存在差异，适合初评集的小样本覆盖。

## 草稿分布

当前 `week3_annotation_draft.jsonl` 共 27 条：

- 建议正样本 15 条；
- 建议负样本 12 条；
- block 19 条、table 8 条；
- 正样本包含 trend、comparison、composition 和 table；
- 负样本覆盖 mixed unit、single number、administrative number、
  non-composition percentages 和 single-point signal。

所有记录均为 `review_status=pending`。机器建议保存在 `suggested`，正式字段保持空值，
避免将当前系统预测误当作 gold。

## 人工审核入口

审核 `data/evaluation/visualization/week3_annotation_review.md`。每条只需确认：

1. 应生成还是拒绝；
2. 若生成，visual type、intent、chart type、指标/时期/单位是否正确；
3. 若拒绝，reason code 是否正确；
4. 有歧义时标记“需讨论”。

字符 span、table 行列坐标和 Decimal 值由确定性程序生成，不需要人工重新计算。

## 工具

- `tools/prepare_visualization_annotations.py`：可复现生成草稿与审核清单；
- `tools/evaluate_visualization_extraction.py`：拒绝未审批 gold，并在审批后计算候选、结构、
  数值、拒绝和工程指标。

人工审核完成后的首版指标见
`docs/delivery/week3_t3.3_baseline_evaluation.md`。当前正样本数量不足计划目标，仍需补充正样本
后才能把本轮结果用于稳定性声明。
