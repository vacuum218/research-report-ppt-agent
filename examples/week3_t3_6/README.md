# Week 3 T3.6 固定联调片段

本目录冻结三个正向场景和两个拒绝场景。正向数值来自
`data/reports/agent/002544_2025-10-28.md` 及人工审核的表格证据。

- 三期盈利预测：生成 `bar`，避免把低信息密度序列默认画成折线图；
- 完整可比公司估值表：生成原生 `table`；
- 完整业务构成表：生成 `pie`；
- 单一百分比：拒绝；
- 金额与百分比混合：拒绝。

`outline.json` 不预填 `visual_candidates`，用于验证 Candidate Locator 能从
slide-scoped evidence 主动发现三个正向场景，并忽略两个拒绝场景。
