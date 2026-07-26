# Research Report PPT Agent

把 PDF、Markdown 或 TXT 研报转换为可编辑 PPTX 的研究型工程。当前仓库已经具备可追溯的
`DocumentBundle`、LLM Slide Outline、确定性可视化生成、布局编译和 PPTX 渲染链路；
编辑决策、统一页面编排、渲染后 QA 与局部修复仍属于下一阶段重构目标。

> 当前状态不是“目标架构已完成”。开发与验收边界以
> [重构实施要求](docs/architecture/research_report_ppt_refactor_spec.md) 为准。

## 当前实现

```text
PDF ── MinerU / raw artifacts ──┐
                                ├─→ DocumentBundle（唯一事实来源）
Markdown / TXT ─────────────────┘             │
                                               ▼
                                  Document Intelligence
                                  （确定性索引与 evidence）
                                               │
                                               ▼
                                  Context Compression +
                                  LLM Slide Planning
                                               │
                                               ▼
                                  Candidate Detection +
                                  Visualization Planning
                                               │
                                               ▼
                                  Deterministic Fact Mapping /
                                  Verification / Numeric Audit
                                               │
                                               ▼
                                  Layout Compiler → PPT Renderer
                                               │
                                               ▼
                                              PPTX
```

已实现的关键约束：

- `DocumentBundle` 是正式上游事实来源；PDF 保留页码与 bbox，Markdown/TXT 使用行号定位。
- `document_intelligence/` 保序、确定、无 LLM，也不持久化用户或跨任务 memory。
- Outline 只表达页面语义、来源和视觉意图，不拥有图表数值或模板坐标。
- 可视化数值由原始 block/table/figure 确定性提取和验证，并生成数值审计记录。
- Compiled Plan 决定具体渲染操作；Compiled Renderer 不重新推断布局。
- `run-pipeline` 在成功时原子发布，任一现有 P0 校验失败时不发布 PPTX。
- Renderer 当前支持原生 chart、table 和 source image。

## 目标架构与当前缺口

目标链路将演进为：

```text
Input Adapter → Canonical Source Model → ReportMap → DeckStoryboard
→ CandidatePool → MetricGroup → EditorialVisualDecision → VisualPortfolio
→ PageSpec / Page Composer → Visualization → Layout Compilation
→ PPTX Rendering → Render QA → Local Page Repair → Published PPTX
```

| 能力 | 当前状态 | 后续方向 |
|---|---|---|
| 统一事实输入 | 已实现为 `DocumentBundle` | 演进为完整 Canonical Source Model |
| 研报理解与故事线 | Outline Generator 同时承担多项职责 | 拆分 `ReportMap` 与 `DeckStoryboard` |
| 视觉候选 | 已有确定性 Candidate Locator | 改为高召回、可审计的 `CandidatePool` |
| 指标语义 | 已有 Numeric Fact Ledger | 增加 typed metric 与 `MetricGroup` 校验 |
| 编辑选择 | 尚无独立决策层 | 增加 `EditorialVisualDecision` 与 Portfolio 预算 |
| 页面编排 | 以布局编译和文字分页为主 | 增加统一 Page Composer、表格/视觉分页与 preflight |
| 渲染质量 | 结构、边界和可打开性测试为主 | 增加页面图像、文字裁切、字号、重叠和清晰度 QA |
| 失败诊断 | Pipeline 失败会清理 staging | 保留轻量诊断包和最后成功阶段 |
| 布局链路 | Legacy Layout Map 与 Compiled Plan 并存 | 分阶段淘汰运行时布局推断 |

因此，“JSON Schema 合法”“PPTX 可以打开”只是当前工程门槛，不等同于最终 deck-level
质量验收。不要把目标规范中的 ReportMap、Visual Decision、Page Composer 或 Render QA
当作现有公开接口。

## 环境安装

项目统一使用 Python 3.12。仓库不提交虚拟环境，也不要复用其他机器复制来的 `.venv`。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PDF 在线解析需要通过环境变量提供 `MINERU_API_TOKEN`。Outline 在线生成默认读取
`DEEPSEEK_API_KEY`，并可通过 `DEEPSEEK_MODEL`、`DEEPSEEK_BASE_URL` 和
`DEEPSEEK_API_PROVIDER` 调整服务。不要把 Token 写入源码、命令参数、输出 JSON 或日志。

## 快速开始

以下命令均在仓库根目录执行。

### 1. 构建 DocumentBundle

Markdown 或 TXT：

```powershell
.\.venv\Scripts\python.exe main.py document-bundle from-markdown `
  data/reports/agent/002544_2025-10-28.md `
  output/002544/document_bundle
```

PDF + MinerU API：

```powershell
.\.venv\Scripts\python.exe main.py document-bundle parse report.pdf `
  --output-root output
```

已有 MinerU `layout.json`、`content_list.json`、`model.json` 和 `document.md` 时：

```powershell
.\.venv\Scripts\python.exe main.py document-bundle from-raw `
  report.pdf RAW_DIRECTORY output/report/document_bundle
```

### 2. 生成或检查 Outline

`--dry-run` 只构造模型请求，不调用外部 LLM：

```powershell
.\.venv\Scripts\python.exe main.py generate-outline `
  output/002544/document_bundle `
  --dry-run
```

在线生成时移除 `--dry-run` 并使用 `-o output/002544/slide_outline.json`。长研报可通过
`--max-tokens 24000` 调整 Outline 响应预算。

### 3. 单命令 Pipeline

先从受控模板生成 Template Profile：

```powershell
.\.venv\Scripts\python.exe main.py build-template-profile `
  templates/template_layout_map.json `
  templates/financial_report_template_v1.pptx `
  -o output/template_profile.json
```

再运行完整现有链路：

```powershell
.\.venv\Scripts\python.exe main.py run-pipeline `
  data/reports/agent/002544_2025-10-28.md `
  --template-profile output/template_profile.json `
  --output-dir output/002544_run
```

需要离线回归或复用已审核 Outline 时增加：

```powershell
--outline-input examples/generated/002544_2025-10-28_slide_outline.json
```

目标输出目录必须不存在或为空。成功输出包括：

```text
document_bundle/
slide_outline.json
numeric_fact_ledger.json
numeric_audit.json
visualization_warnings.json
template_profile.json
visualizations/
compiled_layout_plan.json
presentation.pptx
run_manifest.json
```

Candidate Locator 主动发现但未通过确定性校验的候选会被跳过并写入
`visualization_warnings.json`；Outline 明确要求的视觉若无法生成，则阻断发布。

Compiled Plan 内容页按 Abstract Layout 声明的最小字号容量分页；内容超过容量时生成
`__cont_XX` 续页，视觉保留在第一页，后续页承接剩余文本。Compiled Renderer 禁止通过
PowerPoint 自动缩字把文字压到字号下限以下。

## 分阶段命令

调试时可分别执行：

```powershell
# 可视化生成
.\.venv\Scripts\python.exe main.py generate-visualizations `
  output/002544/slide_outline.json `
  output/002544/document_bundle `
  -o output/002544/visualizations

# 编译布局
.\.venv\Scripts\python.exe main.py compile-layout `
  output/002544/slide_outline.json `
  output/002544/visualizations/visualization_manifest.json `
  output/template_profile.json `
  -o output/002544/compiled_layout_plan.json

# 严格执行 Compiled Plan
.\.venv\Scripts\python.exe main.py render-compiled-plan `
  output/002544/compiled_layout_plan.json `
  -o output/002544/presentation.pptx
```

`render-ppt`、`parse-report` 和 Legacy Layout Map 仍为兼容入口。新功能应优先接入
`DocumentBundle → run-pipeline → Compiled Plan` 链路；不要再以 Parsed Document JSON
作为新的正式输入契约。

## 数据契约

DocumentBundle 的正式下游接口是 `document.json` 与 `assets/`：

```text
document_bundle/
├── document.json
├── validation.json
├── assets/
│   ├── figures/
│   └── tables/
└── raw/
    ├── layout.json
    ├── content_list.json
    ├── model.json
    └── document.md
```

主要 Schema：

- `schemas/document_bundle.schema.json`
- `schemas/slide_outline.schema.json`
- `schemas/visualization.schema.json`
- `schemas/visualization_manifest.schema.json`
- `schemas/template_profile.schema.json`
- `schemas/compiled_layout_plan.schema.json`
- `schemas/run_manifest.schema.json`
- `schemas/parsed_document.schema.json`（deprecated，仅用于兼容回归）

修改 Schema 时必须同步 loader、validator、样例、测试和迁移说明。不得把目标架构字段直接
塞入冻结的旧契约来规避版本迁移。

## 项目结构

| 路径 | 职责 |
|---|---|
| `document_bundle/` | PDF/Markdown/TXT 统一事实输入与资产物化 |
| `document_intelligence/` | 确定性索引、evidence、figure inventory 与 chunk |
| `outline_generator/` | 运行时 context compression 与 LLM slide planning |
| `visualization_generator/` | 候选发现、事实抽取、验证、审计和 manifest |
| `pipeline_runner/` | 单命令编排、当前原子发布和 run manifest |
| `ppt_engine/` | 布局解析、文字分页、编译与 chart/table/image 渲染 |
| `ppt_template_parser/` | PPT 模板对象、样式与主题分析 |
| `compat/structured_content/` | deprecated 的 DocumentBundle→Parsed Document 适配器 |
| `document_parser/` | Markdown/TXT 解析实现及旧 Parsed JSON CLI 兼容 |
| `schemas/`、`prompts/` | 冻结数据契约、Outline prompt 与 few-shot cases |
| `templates/`、`layouts/` | 受控模板、Legacy Layout Map 与抽象布局目录 |
| `tools/` | 校验、模板构建和历史验收工具 |
| `tests/`、`examples/` | 单元/集成回归与受控样例 |
| `data/` | 真实研报基线、人工对照与评估数据，不存放运行生成物 |
| `docs/` | 长期规范、实施计划与历史交付记录 |

## 测试与验收

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q
```

自动化测试使用 MockTransport 模拟 MinerU，不需要真实 API Token。PPT 集成测试会重新打开
输出文件并检查页数以及 chart、table、image 和文本对象，但目前不等同于像素级 Render QA。

提交主链路改动前还应至少确认：

- 数值、单位、时期和来源可以回查到原始 evidence；
- mixed metric、mixed measure kind、低信息量序列等负样本被拒绝；
- 每页视觉不超过当前布局容量，required 内容没有静默丢失；
- 最终 PPTX 可重新打开，且人工检查无明显裁切、重叠、空洞或图文不相关；
- 失败不会被误报为已发布的有效 PPTX。

## 文档入口

- [目标架构与重构实施要求](docs/architecture/research_report_ppt_refactor_spec.md)
- [当前系统概览](docs/architecture/system_overview.md)
- [接口规范](docs/architecture/interfaces.md)
- [DocumentBundle 规范](docs/specs/document_bundle.md)
- [文档导航](docs/README.md)

`docs/delivery/` 中的周次记录是历史验收证据，其中的命令、测试数量和旧 Parsed Document
路径不代表当前推荐入口。
