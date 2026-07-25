# Week 3 T3.6 固定联调片段

本目录冻结三项正向场景和两项拒绝场景。正向数值来自
`data/reports/agent/002544_2025-10-28.md` 及其已人工审核的 Week 3 表格证据。

- paragraph 盈利预测：生成 line；
- complete table 可比公司估值：生成原生 table；
- complete table 业务构成：生成 pie；
- 单一百分比：拒绝；
- 金额与百分比混合：拒绝。

`outline.json` 不预填 `visual_candidates`，用于验证 Candidate Locator 能从
slide-scoped evidence 主动发现三个正向场景，并忽略两个拒绝场景。
