# Research Report PPT Agent

## Project Introduction

Research Report PPT Agent 是一个将“研究报告文本 → 自动生成可视化 PowerPoint”
的 Python 系统。输入上市公司 Markdown 研报后，系统依次完成文本结构化、PPT
语义大纲生成、图表/表格数据生成、模板版式选择和 PPTX 渲染。

核心边界：Slide Outline 只回答“这一页讲什么”，Visualization JSON 提供真实绘图
数据，Layout Resolver 选择模板，Renderer 负责生成最终 PowerPoint。

## Features

- Markdown/纯文本研报解析
- 自动生成 PPT 语义大纲
- 自动识别 chart/table 可视化需求
- 基于原文证据生成 Chart/Table 数据
- 固定 PowerPoint 模板渲染
- 基于业务语义的 Layout 匹配
- Outline、Visualization 和 Layout Map 校验
- 输出可重新打开、可继续编辑的 `.pptx`

## Architecture

```text
Research Report Markdown
        │
        ▼
Document Parser
        │
        ▼
Parsed Document JSON
        │
        ▼
Slide Outline Generator
        │
        ▼
Slide Outline JSON
        │
        ▼
Visualization Generator
        │
        ▼
Visualization JSON
        │
        ▼
Layout Resolver
        │
        ▼
PPT Renderer
        │
        ▼
Final PPTX
```

### 1. Document Parser

- 输入：Markdown 或纯文本研报。
- 输出：符合 `schemas/parsed_document.schema.json` 的 Parsed Document JSON。
- 职责：提取标题、段落、列表、表格，以及 source、block、行号和章节层级信息。

### 2. Slide Outline Generator

- 输入：Parsed Document JSON。
- 输出：符合 `schemas/slide_outline.schema.json` 的 Slide Outline JSON。
- 职责：生成 `slide_id`、`title`、`key_message`、`bullet_points`、
  `slide_type`、`page_role`、`layout_hint`、`visual_candidates` 和 `source_refs`。

Slide Outline 只描述“这一页讲什么”。它不保存坐标、字体、颜色或 chart/table
具体数值。

### 3. Visualization Generator

- 输入：Slide Outline JSON + Parsed Document JSON。
- 输出：符合 `schemas/visualization.schema.json` 的独立 Visualization JSON 文件。
- 职责：结合 `visual_candidates`、`source_refs` 和原文数据，为 Chart 生成
  `chart_type`、`categories`、`series`、`values`，为 Table 生成 `columns` 和 `rows`。

Visualization JSON 是 Renderer 的实际绘图数据来源。生成器找不到可追溯原文数据时
会输出 warning，不会把数据写回 Slide Outline，也不会编造数据。

### 4. Layout Resolver

Layout Resolver 根据以下语义信息选择模板 `layout_id`：

```text
page_role special rules
        ↓
slide_type + visual_candidates + layout_hint
        ↓
slide_type defaults
        ↓
fallback
```

典型映射：

```text
industry_analysis + chart  → industry_outlook
financial_forecast + table → earnings_forecast
valuation_analysis + table → valuation_comparison
```

### 5. PPT Renderer

- 输入：Slide Outline JSON + Visualization JSON + Template Layout Map + PPT 模板。
- 输出：最终 PPTX。
- 职责：根据已解析的 `layout_id` 克隆模板页、填充文本，并将完整 Visualization
  JSON 渲染到对应 chart/table 区域。

Renderer 不从 `visual_candidates` 生成数据。若版式和 Outline 要求可视化但没有绑定
对应 Visualization JSON，CLI 会在进入 Renderer 前输出明确 warning。

## Installation

要求 Python 3.10 或更高版本：

```powershell
python -m pip install -r requirements.txt
```

生成 Slide Outline 需要 DeepSeek API Key：

```powershell
$env:DEEPSEEK_API_KEY = "<your-api-key>"
```

## Quick Start

以下命令均在仓库根目录执行，示例输入为：

```text
data/reports/agent/002544_2025-10-28.md
```

### Step 1：Markdown → Parsed Document JSON

CLI 最简命令：

```powershell
python main.py parse-report data/reports/agent/002544_2025-10-28.md
```

未指定 `-o` 时，实际输出为：

```text
data/reports/agent/002544_2025-10-28_parsed.json
```

为统一将运行产物保存在 `output/`，推荐执行：

```powershell
python main.py parse-report `
  data/reports/agent/002544_2025-10-28.md `
  -o output/parsed/002544_2025-10-28_parsed.json
```

### Step 2：Parsed Document JSON → Slide Outline JSON

```powershell
python main.py generate-outline `
  output/parsed/002544_2025-10-28_parsed.json `
  -o output/outlines/002544_2025-10-28_slide_outline.json
```

输出：

```text
output/outlines/002544_2025-10-28_slide_outline.json
```

建议在进入下一阶段前校验：

```powershell
python main.py validate-outline `
  output/outlines/002544_2025-10-28_slide_outline.json
```

如果不传 `-o`，当前 CLI 默认输出到 `output/outlines/`，并按照输入文件名生成
`002544_2025-10-28_parsed_outline.json`。

### Step 3：生成 Visualization JSON

```powershell
python main.py generate-visualizations `
  output/outlines/002544_2025-10-28_slide_outline.json `
  output/parsed/002544_2025-10-28_parsed.json `
  -o output/visualizations
```

输出目录示例：

```text
output/visualizations/
├── slide_004__visual_001.json
├── slide_006__visual_002.json
├── slide_007__visual_003.json
├── slide_008__visual_004.json
├── slide_009__visual_005.json
└── visualization_manifest.json
```

终端会为每个文件打印对应的 `--visualization slide_id=file.json` 参数。
`visualization_manifest.json` 记录 slide、候选、原文 block 和文件之间的绑定关系。

### Step 4：Visualization JSON + Outline → Final PPTX

```powershell
python main.py render-ppt `
  output/outlines/002544_2025-10-28_slide_outline.json `
  --visualization slide_004=output/visualizations/slide_004__visual_001.json `
  --visualization slide_006=output/visualizations/slide_006__visual_002.json `
  --visualization slide_007=output/visualizations/slide_007__visual_003.json `
  --visualization slide_008=output/visualizations/slide_008__visual_004.json `
  --visualization slide_009=output/visualizations/slide_009__visual_005.json `
  -o output/ppt/final.pptx
```

`--visualization` 参数格式为：

```text
slide_id=file.json
```

例如：

```text
slide_006=output/visualizations/slide_006__visual_002.json
```

最终输出：

```text
output/ppt/final.pptx
```

参数可以重复传入。实际运行时应以 Step 3 的终端输出或
`visualization_manifest.json` 为准，将成功生成的 Visualization 文件全部绑定到对应页面。

## Repository Structure

```text
├── data/                     # 原始研报和测试数据
│   └── reports/              # Markdown/纯文本研报
├── output/                   # 本地运行产生的中间结果与最终结果（不提交 Git）
│   ├── parsed/               # Parsed Document JSON
│   ├── outlines/             # Slide Outline JSON
│   ├── visualizations/       # Visualization JSON 与 Manifest
│   └── ppt/                  # 最终 PPTX
├── document_parser/          # Markdown/纯文本结构化解析
├── outline_generator/        # LLM Slide Outline 生成与校验重试
├── visualization_generator/  # Chart/Table 数据生成与渲染前覆盖检查
├── ppt_engine/               # Layout Resolver、模板页构建和 PPTX 渲染
├── ppt_template_parser/      # 已有 PPT 模板结构、样式和主题解析
├── templates/                # PPT 模板和 template_layout_map.json
├── schemas/                  # Parsed Document、Outline、Visualization JSON Schema
├── prompts/                  # Outline Generator Prompt 与 few-shot
├── tools/                    # Schema 校验、模板盘点和 Layout Map 工具
├── examples/                 # 合法 JSON 与正式生成样例
├── tests/                    # unit、integration 和 fixtures
├── docs/                     # 架构、规范、评审和交付记录
├── main.py                   # 统一 CLI 入口
└── requirements.txt          # Python 依赖
```

`output/` 已被 `.gitignore` 忽略。上述子目录由对应命令在写入结果时自动创建，
无需预先手工建立。

## Validation

运行全部自动测试：

```powershell
python -m pytest -q
```

当前最终验证结果为 `127 passed`。自动测试不会调用真实 DeepSeek API；正式验收使用
真实研报和已验收的 Outline 产物验证后续 Visualization、Layout、Renderer 链路。

最终 Pipeline 验收记录见
[docs/delivery/final_pipeline_validation.md](docs/delivery/final_pipeline_validation.md)。

## Interface Rules

- `schemas/slide_outline.schema.json` 和 `schemas/visualization.schema.json` 是冻结接口。
- Slide Outline 不包含模板信息、坐标、样式或图表具体数值。
- Visualization JSON 不包含模板 layout 或 Shape 信息。
- Layout Resolver 只选择 `layout_id`。
- Renderer 只根据 Outline、完整 Visualization JSON 和模板映射生成 PPTX。
- API Key 只能通过环境变量提供，不提交请求、响应、reasoning 或临时运行产物。
