# Week 3 T3.6 端到端联调与数值审计

- 日期：2026-07-25
- 实现状态：**代码修改完成**
- 自动测试：**等待用户手动运行**
- 视觉审核：**等待生成验收 Deck**

## 固定场景

`examples/week3_t3_6/` 冻结三个正向场景和两个拒绝场景：

1. paragraph 中的 2025—2027 年归母净利润预测，生成原生 line；
2. complete table 可比公司估值，生成原生 table；
3. complete table 三项业务占比，生成原生 pie；
4. 单一百分比，拒绝；
5. 金额与百分比混合且无换算关系，拒绝。

片段来自 `data/reports/agent/002544_2025-10-28.md` 及已人工审核的 Week 3
表格证据。固定 Outline 不预填 `visual_candidates`，三个正向场景必须由 Candidate
Locator 主动发现。

## 数值审计

`visualization_generator/audit.py` 提供旁路审计，不修改正式 Visualization Schema。
生成阶段在内存中保存每个 `fact_id` 对应的最终 JSON 路径；审计时重新从 Numeric Fact
Ledger 解析该事实，并使用 Decimal 比较最终输出值。

审计记录包含：

- evidence kind/id；
- `fact_id`；
- 原文值和规范化值；
- 单位、标签及期间；
- block span 或 table 行列坐标；
- Visualization 输出路径和输出值；
- 单项核对状态。

数值不一致、fact 不存在、输出路径不存在或数值型 Visualization 缺少 fact 绑定时，
验收脚本明确失败。正式 Visualization JSON 不携带内部 `fact_id`。

## 验收产物

运行：

```powershell
python tools/build_week3_t3_6_end_to_end.py
```

默认生成：

```text
output/week3_t3.6_end_to_end/
├── numeric_fact_ledger.json
├── numeric_audit.json
├── scenario_results.json
├── template_profile.json
├── visualizations/
│   ├── visualization_manifest.json
│   └── *.json
├── compiled_layout_plan.json
└── week3_t3.6_end_to_end.pptx
```

## 自动验收

新增 `tests/integration/test_week3_t3_6_end_to_end.py`，覆盖：

- 三个正向场景的主动发现和类型；
- 两个拒绝场景不产生 plan 或 Visualization；
- 所有输出数值通过 Decimal 审计；
- 将首个趋势值篡改为 `999` 后审计明确失败；
- Manifest、Template Profile 和 Compiled Layout Plan 可串联；
- PPTX 重开后包含 2 个原生 chart 和 1 个原生 table。

用户手动运行：

```powershell
python -m pytest tests/integration/test_week3_t3_6_end_to_end.py -q
python -m pytest tests/unit/test_visualization_extraction.py tests/unit/test_visualization_verification.py tests/unit/test_visualization_renderer.py tests/unit/test_table_renderer.py -q
python -m pytest -q
python tools/build_week3_t3_6_end_to_end.py
```

## 人工审核

打开 `output/week3_t3.6_end_to_end/week3_t3.6_end_to_end.pptx` 后检查：

1. 第一页 line 的三个年份和数值是否正确；
2. 第二页 table 是否为可编辑原生表格，内容是否居中且没有截断；
3. 第三页 pie 是否为三项业务构成且合计约 100%；
4. 第四、五页是否没有生成图表或表格；
5. `numeric_audit.json` 的 `status` 是否为 `passed`、`mismatch_count` 是否为 0。

自动测试与人工视觉审核均通过后，T3.6 才可标记为正式完成。
