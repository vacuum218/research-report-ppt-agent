# Week 3 Visualization 初评集标注指南

本目录用于 T3.3 的 20–30 条初评 evidence unit。标注必须在针对样本调参前冻结版本；后续修正
需要在评估报告中记录原因。

## 当前审核流程

自动准备命令：

```powershell
python tools/prepare_visualization_annotations.py
```

该命令固定从三份研报生成：

- `week3_annotation_draft.jsonl`：机器预标注，`review_status=pending`；
- `week3_annotation_review.md`：人工审核清单。

预标注只能作为审核起点，不能改名后直接充当 gold。人工审核完成后，应把每条记录的
`should_visualize`、`expected` 或 `rejection_code` 定稿，将 `review_status` 改为
`approved`，删除 `suggested`，再保存为 `week3_gold.jsonl`。

正式 gold 校验：

```powershell
python tools/evaluate_visualization_extraction.py `
  --gold data/evaluation/visualization/week3_gold.jsonl
```

评估预测：

```powershell
python tools/evaluate_visualization_extraction.py `
  --gold data/evaluation/visualization/week3_gold.jsonl `
  --predictions OUTPUT_PREDICTIONS.jsonl `
  --output OUTPUT_REPORT.json
```

预测文件按 `sample_id` 对齐，使用与 gold 相同的 `should_visualize`、`expected` 和
`rejection_code` 字段；成功生成的记录另填 `schema_valid: true`。评估工具会报告候选
Precision/Recall/F1、结构准确率、数值单元格指标、正确拒绝率、Schema 和来源覆盖计数。

当前冻结产物：

- `week3_gold.jsonl`：27 条人工审核记录，15 正/12 负；
- `week3_baseline_predictions.jsonl`：与最终 Gold 对齐的审核前冻结预测；
- `week3_baseline_report.json`：平衡集基线评估结果；
- `week3_initial_gold.jsonl` / `week3_initial_baseline_predictions.jsonl`：
  首轮审核的不可变合并输入；
- `week3_positive_supplement_gold.jsonl`：补充批次的 7 正/1 负审核结果。

当前 Gold 覆盖 5 份报告、10 个 chart 正样本、5 个 table 正样本和 12 个负样本，达到计划的
数量与来源覆盖要求。

正样本补充批次位于：

- `week3_positive_supplement_draft.jsonl`；
- `week3_positive_supplement_review.md`；
- `week3_positive_supplement_baseline_predictions.jsonl`。

补充批次共 8 个未使用的 complete table，人工接受 7 条、拒绝 1 条。合并时首先保留冻结基线
误报，再按拒绝原因、报告和来源类型增加覆盖，确定性保留 12 条负样本：

```powershell
python tools/merge_visualization_gold.py --negative-limit 12
```

## 标注单位

一条 JSONL 记录对应一个原生 `block` 或一个 `complete table`，不是任意切分的句子。相同来源
若包含两个互不相关的指标关系，可以用不同 `sample_id` 标注，但必须明确目标 evidence。

初评集总计 20–30 条，并尽量满足以下分布（正负样本数量之和不得超过 30）：

- 15–18 条应生成可视化的正样本；
- 12–15 条不应生成的负样本；
- 覆盖至少 3 份研报；
- 同时包含 paragraph 和 complete table；
- 覆盖趋势、比较、构成、多系列、混合单位、缺失值和干扰数字。

## JSONL 字段

每行是一个 JSON object：

```json
{
  "sample_id": "week3_001",
  "document_id": "report_001",
  "source": {"kind": "block", "id": "p004-b011"},
  "section_id": "sec-003",
  "evidence": {
    "text": "2022年收入10亿元，2023年收入15亿元。",
    "table": null
  },
  "should_visualize": true,
  "expected": {
    "visual_type": "chart",
    "chart_intent": "trend",
    "chart_type": "line",
    "title": "营业收入趋势",
    "unit": "亿元",
    "categories": ["2022", "2023"],
    "series": [
      {
        "name": "营业收入",
        "facts": [
          {"raw_value": "10", "normalized_value": "10", "source_locator": {"start": 7, "end": 9}},
          {"raw_value": "15", "normalized_value": "15", "source_locator": {"start": 18, "end": 20}}
        ]
      }
    ]
  },
  "rejection_code": null,
  "notes": ""
}
```

规则：

- `source.kind` 只允许 `block | table`。
- paragraph 使用 `evidence.text`，table 使用 `evidence.table`；未用字段为 `null`。
- `normalized_value` 用十进制字符串保存，避免 JSON 浮点误差。
- block fact 的 `source_locator` 使用 `[start, end)`；table fact 使用零基
  `{"row_index": 1, "column_index": 2}`。
- 正样本填写 `expected`，`rejection_code` 为 `null`。
- 负样本的 `expected` 为 `null`，并使用
  `visualization_generator.contracts.CandidateRejectionCode` 中的一个 code。
- 单位无法证明时不得由标注者推断换算；样本应标记为拒绝。
- title 可按证据作轻量规范化，但指标、期间、分类和数值不得由常识补全。

## 匹配与计数

Candidate 以 `(source kind/id, visual_type, chart_intent)` 为主匹配键。一个预测最多匹配一个
gold，一个 gold 也最多匹配一个预测。文字相似度只可用于错误分析，不能改变 TP/FP/FN。

每份报告必须输出：

- Candidate TP、FP、FN 及 Precision/Recall/F1；
- chart type 和结构字段准确率；
- 数值单元格 TP、FP、FN、Precision/Recall/Exact Match；
- 完整对象正确数/对象总数；
- 正确拒绝数/负样本总数；
- Schema、sources、无来源数值和编造数值的 P0 计数。
