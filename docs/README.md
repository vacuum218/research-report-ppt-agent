# 项目文档导航

本目录按文档生命周期分类。长期有效的设计规范与阶段性验收记录分开维护，
避免历史材料被误当成当前实现。

## 架构与接口

- [项目上下文](architecture/project_context.md)
- [系统架构](architecture/system_overview.md)
- [接口规范与开发规则](architecture/interfaces.md)

## 数据与模板规范

- [DocumentBundle v0.1](specs/document_bundle.md)
- [Document Intelligence Layer](specs/document_intelligence.md)
- [Slide Outline Schema 说明](specs/slide_outline.md)
- [Visualization Schema 说明](specs/visualization.md)
- [PPT 模板版式与占位区域](specs/template_layout.md)

JSON Schema 文件本身位于仓库根目录 `schemas/`，并且优先级高于解释性文档。

## 计划与质量

- [项目任务计划](planning/task_plan.md)
- [Week 3 可视化内容定位与抽取执行计划](planning/week3_visualization_execution_plan.md)
- [原始周计划与任务跟踪表](planning/研报PPT生成项目_周计划与任务跟踪.xlsx)
- [验收标准与风险](quality/acceptance_and_risk.md)

## 评审与交付

- [T2.3 正式样例评审记录](reviews/T2.3_002544_outline_review.md)
- [当前项目代码交付说明](delivery/week2_t2.1-t2.3_partner_handoff.md)
- [T2.4/T2.5 基础 PPT Engine 交付说明](delivery/week2_t2.4-t2.5_handoff.md)
- [最终 Pipeline 验收记录](delivery/final_pipeline_validation.md)
- [Week 3 T3.0 接口与验收口径冻结](delivery/week3_t3.0_contract_freeze.md)
- [Week 3 T3.1 Candidate Locator 交付记录](delivery/week3_t3.1_candidate_locator.md)
- [Week 3 T3.2 数值事实、结构映射与校验](delivery/week3_t3.2_fact_extraction_verification.md)
- [Week 3 T3.3 预标注与评估工具交付](delivery/week3_t3.3_annotation_draft_handoff.md)
- [Week 3 T3.3 平衡 Gold 与冻结基线评估](delivery/week3_t3.3_baseline_evaluation.md)
- [Week 3 T3.3 正样本补充审核与合并](delivery/week3_t3.3_positive_supplement_handoff.md)
- [Week 3 T3.4 原生图表能力与样式验收](delivery/week3_t3.4_native_chart_handoff.md)
- [Week 3 T3.5 原生表格样式与容量验收](delivery/week3_t3.5_native_table_handoff.md)
- [Week 3 T3.6 端到端联调与数值审计](delivery/week3_t3.6_end_to_end_audit.md)
- [Week 3 T3.7 单命令 Pipeline 与回归](delivery/week3_t3.7_single_command_pipeline.md)

当前代码结构、命令和路径以根目录 README、`requirements.txt`、`main.py`
和本导航中的长期规范为准。

## Phase 1

- [Typed metric migration and offline acceptance](delivery/phase1_typed_metric_migration.md)
