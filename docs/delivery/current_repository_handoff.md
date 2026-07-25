# Research Report PPT Agent 当前代码仓库交接文档

> 盘点日期：2026-07-23  
> 当前分支：`unfixedversion`  
> 当前提交：`126f2c6`（`temple`）  
> 对照分支：本分支比本地 `master` 领先 1 个提交  
> 盘点原则：以当前代码、JSON Schema 和自动化测试为准；历史交付文档只作背景参考

## 1. 交接结论

本仓库已经具备从 PDF、Markdown 或纯文本研报到模板化 PPTX 的分阶段实现，主要链路为：

```text
PDF / Markdown / Text
        ↓
DocumentBundle
        ↓
Document Intelligence
        ↓
LLM Context Compression / Direct Context
        ↓
Slide Outline
        ↓
Visualization Planning
        ↓
Deterministic Visualization Generator
        ↓
Visualization Manifest
        ↓
Template Profile + Layout Compiler
        ↓
Compiled Layout Plan
        ↓
Compiled-plan Renderer
        ↓
PPTX
```

当前不是“只有解析器和大纲生成器”的早期版本。Visualization、模板映射、图表/表格/图片渲染、
Template Profile、Layout Compiler 和 Compiled Layout Plan 均已有代码与测试。

截至本次盘点：

- 全量自动化测试：`239 passed`（最终复核耗时 15.34 秒）；
- 测试文件：35 个，其中 `tests/unit/` 17 个、`tests/integration/` 8 个、
  `tests/document_bundle/` 10 个；
- GitHub Actions 已配置 Linux/Python 3.10、Linux/Python 3.12、
  Windows/Python 3.11 测试矩阵；
- 工作区原有 `.venv` 已失效，不能直接使用；
- 本地 `output/` 中存在大量实验产物，但该目录被 Git 忽略，且部分产物与当前 Schema 不兼容，
  不能视作代码基线；
- 当前仓库没有配置 Git remote。

## 2. 当前成熟度与边界

| 能力 | 状态 | 说明 |
|---|---|---|
| Markdown/纯文本解析 | 已实现 | 可生成正式 DocumentBundle；旧 Parsed Document CLI 仍保留 |
| PDF 在线解析 | 已实现 | 依赖 MinerU API v4 和 `MINERU_API_TOKEN` |
| MinerU raw 重建 | 已实现 | 可用四个 raw 文件确定性重建 bundle |
| Document Intelligence | 已实现 | 纯确定性、只读、运行时索引与分块 |
| Slide Outline 生成 | 已实现 | OpenAI-compatible HTTP 接口，支持 DeepSeek/SiliconFlow 请求方言 |
| Outline dry-run | 已实现 | 可预览完整请求，不调用 LLM |
| Visualization Planning | 已实现 | 只描述意图，不产生事实数值或资源路径 |
| Chart/Table/Image 生成 | 已实现 | 数据必须来自 DocumentBundle 原生证据 |
| Visualization Manifest v3 | 已实现 | 固化页面绑定、来源、文件和上游 hash |
| Legacy Layout Map Renderer | 已实现并保留 | `render-ppt` 运行时仍会进行版式解析 |
| Template Profile | 已实现 | 从 Layout Map 和 PPTX 模板确定性生成 |
| Layout Compiler | 已实现 | 产出显式、可校验的 Compiled Layout Plan |
| Compiled-plan Renderer | 已实现 | 按 operation 执行，不做版式推断 |
| 原生 PPT 图表/表格 | 已实现 | 图表支持 line/column/bar/area/pie |
| 原始图片渲染 | 已实现 | 等比缩放、居中放入槽位，限制资源路径逃逸 |
| 单命令完整流水线 | 未实现 | 当前需要逐阶段执行和记录产物 |
| 复杂自动排版/溢出拆页 | 不完整 | 容量主要由模板规则和 Compiler 前置检查控制 |
| 生产级可观测性 | 不完整 | 主要使用 stdout/stderr，没有统一运行记录或指标系统 |

## 3. 代码目录与职责

```text
main.py                       统一 CLI 分发入口
requirements.txt              Python 依赖

document_bundle/              正式上游数据层
├── cli.py                    PDF、raw、Markdown 三类入口
├── bundle.py                 PDF/raw bundle 编排与原子化 JSON 写入
├── markdown.py               Markdown/Text → DocumentBundle
├── query.py                  DocumentBundle 只读查询接口
├── validation.py             validation.json 和 PDF profile 校验
├── parser/
│   ├── base.py               Parser 抽象
│   ├── mineru_client.py      MinerU API v4 客户端
│   └── artifacts.py          MinerU 结果包处理
└── transform/                blocks、sections、reading order、assets 转换

document_intelligence/        DocumentBundle 上的确定性只读访问层
├── loader.py                 bundle 路径解析与 Schema 校验
├── index.py                  block/section/table/figure/evidence 索引
├── chunking.py               保序、按章节与字符预算分块
└── models.py                 snapshot、chunk、evidence 等运行时模型

outline_generator/            LLM 理解与 Slide Outline 生成
├── generate_outline.py       CLI、请求构造、调用、重试、校验和原子写入
├── llm_understanding.py      context memory 结构与压缩提示
├── bundle_validation.py      section/evidence 后置校验
└── few_shot.py               case library 加载和确定性选择

visualization_generator/      可视化规划、确定性生成及 Manifest
├── planning.py               Outline 意图 → 无数值运行时 plan
├── generator.py              从 bundle 证据生成 chart/table/image
├── manifest.py               Manifest v3 加载、校验和兼容读取
└── generate_visualizations.py CLI、预检、文件和 Manifest 输出

ppt_engine/                   版式选择、编译和渲染
├── layout_resolver.py        Legacy Layout Map 与 Template Profile 版式解析
├── compiler.py               Outline + Manifest + Profile → Compiled Plan
├── compiled_plan.py          Compiled Plan 加载与语义校验
├── renderer.py               Legacy Renderer 和 Compiled-plan Renderer
├── slide_builder.py          模板页复制、字段填充和 operation 执行
└── visualization_renderer.py chart/table/image 的物理渲染

ppt_template_parser/          通用 PPTX 结构、样式和主题解析
tools/                        Schema 校验、模板盘点、Layout Map/Profile 构建
schemas/                      冻结的模块间 JSON 契约
prompts/                      Outline system prompt 和 few-shot case library
templates/                    受版本控制的 PPTX 模板与 Legacy Layout Map
tests/                        单元、集成和 DocumentBundle 测试
docs/                         架构、规范、历史交付和质量文档
data/                         真实研报、参考资料和测试数据
examples/                     小型合法 Outline/Visualization 示例
output/                       本地运行产物；被 Git 忽略
```

## 4. 两条 PPT 生成链路

### 4.1 推荐链路：先编译、后执行

新链路将所有版式选择、内容绑定、可视化槽位匹配和容量检查放在 Compiler 中完成：

```text
Slide Outline
  + Visualization Manifest
  + Template Profile
        ↓
Layout Compiler
        ↓
Compiled Layout Plan
        ↓
Renderer 只执行 operation
```

优势：

- Template Profile 明确声明模板能力，不允许隐式借用其他槽位；
- Manifest 将 Visualization 和 slide、来源、文件绑定起来；
- Compiler 校验 Outline hash、Manifest 绑定、模板能力和可视化容量；
- Compiled Plan 内嵌 Visualization 数据以及全部有序 operation；
- Renderer 校验模板 SHA-256，模板不匹配时直接失败；
- 每个 Visualization 必须被恰好消费一次，不能静默遗漏或重复渲染。

当前支持的 operation 包括：

- `set_text`
- `set_bullets`
- `set_repeated_text`
- `remove_shapes`
- `render_chart`
- `render_table`
- `render_image`

### 4.2 兼容链路：运行时解析 Layout Map

旧链路仍由 `render-ppt` 提供：

```text
Outline + 若干 --visualization slide_id=file.json
  + templates/template_layout_map.json
  + templates/financial_report_template_v1.pptx
        ↓
Layout Resolver
        ↓
Legacy Renderer
        ↓
PPTX
```

此入口仍有测试覆盖，适合小型示例或兼容旧调用者。但它通过重复的
`--visualization slide_id=path` 参数进行绑定，且在渲染阶段仍包含版式解析逻辑。
新开发应优先围绕 Manifest、Template Profile 和 Compiled Plan 扩展。

## 5. 核心数据契约

Schema 使用 JSON Schema Draft 2020-12。跨模块数据变化必须先评估 Schema 和兼容策略，
不能只修改 Python 代码。

| 契约 | 当前版本 | 文件 | 关键约束 |
|---|---:|---|---|
| DocumentBundle | v0.1 | `schemas/document_bundle.schema.json` | 顶层字段冻结，不包含 LLM 内容 |
| Parsed Document | 1.0 | `schemas/parsed_document.schema.json` | deprecated，仅供旧 CLI/compat |
| Slide Outline | 1.0.0 | `schemas/slide_outline.schema.json` | 只回答“每页讲什么”，不含图表数据/坐标 |
| Visualization | 无顶层版本字段 | `schemas/visualization.schema.json` | chart/table/image 三选一 |
| Visualization Manifest | 3.0.0 | `schemas/visualization_manifest.schema.json` | 绑定文件、类型、来源、Outline hash |
| Legacy Layout Map | 1.0 | `templates/template_layout_map.json` | 迁移期保留的模板映射 |
| Template Profile | 1.0.0 | `schemas/template_profile.schema.json` | 显式 layout、binding、slot、capacity |
| Compiled Layout Plan | 1.0.0 | `schemas/compiled_layout_plan.schema.json` | 内嵌可视化和完整 operation 流 |

### 5.1 DocumentBundle

冻结顶层结构：

```json
{
  "document": {},
  "pages": [],
  "blocks": [],
  "sections": [],
  "tables": [],
  "figures": [],
  "reading_order": []
}
```

PDF profile：

- 使用真实 `page + bbox` 定位；
- `raw/` 必须保留 `layout.json`、`content_list.json`、`model.json`、`document.md`；
- 图、表资源从 PDF 确定性裁切；
- `validation.json.status` 可能为 `passed`、`needs_review` 或 `failed`。

Markdown/Text profile：

- 使用 `line_start/line_end` 定位；
- `bbox=null`，不得伪造 PDF 坐标；
- `raw/` 保留原始 `document.md`。

表格分为：

- `complete`：存在结构化 grid，可生成原生 chart/table；
- `image_only`：只保留裁切图，不允许自动补造单元格。

### 5.2 Document Intelligence

`document_intelligence` 是运行时确定性层，不写出新的长期 JSON。它负责：

- 校验并加载 `document.json`；
- 建立 block、section、table、figure 索引；
- 建立 section hierarchy 和 evidence locator；
- 建立 block 与 table/figure 的关系；
- 严格按照 `reading_order` 生成 chunk；
- 在章节变化或字符预算边界处切块。

它明确不负责 summary、importance、key points、slide planning 或 LLM 调用。
所有 block 必须恰好覆盖一次且顺序不变。

### 5.3 Slide Outline

Outline 顶层字段为：

```json
{
  "schema_version": "1.0.0",
  "metadata": {},
  "sources": [],
  "slides": []
}
```

每页至少包括 `slide_id`、`page_role`、`slide_type`、`title`、`key_message`、
`bullet_points`、`source_refs` 和 `visual_candidates`。

`section_ref` 和 `evidence_refs` 为兼容旧 Outline 而保持 optional，但新生成的 section/content
页面会执行 DocumentBundle 后置校验。`visual_candidates` 只表达 chart/table 意图，
不能包含 categories、series、values、columns 或 rows。

`figure_page` 是原始 figure 的独立保真页面：

- `page_role=content`；
- `bullet_points=[]`；
- `visual_candidates=[]`；
- `evidence_refs` 只能有一个 figure；
- 多个 figure 必须拆成多页并保持原文顺序。

### 5.4 Visualization 与 Manifest

Visualization Planning 只保存类型、用途、意图、数据需求和 evidence refs。
Deterministic Generator 才能读取 DocumentBundle 并生成事实数据：

- `complete table` → table 或 chart；
- 含明确数值序列的 block → chart；
- figure → image；
- `image_only table` → image。

每个生成物使用 `sources` 保存原生 `block/table/figure` ID。生成失败时输出
`no_traceable_source_data` 等 issue，不允许猜测或补造数据。

Manifest v3 还保存：

- `outline_sha256`
- `document_source_sha256`
- `asset_root`
- `slide_id`
- `visualization_id`
- `visual_type`
- `sources`
- `visualization_file`

Loader 可只读兼容旧 v2 Manifest，但 Generator 只输出 v3.0.0。

### 5.5 Template Profile 与 Compiled Plan

Template Profile 由当前 PPTX 模板和 Legacy Layout Map 构建，记录：

- 模板文件、尺寸、页数和 SHA-256；
- 可用 operation；
- page role 和 slide type 的版式选择规则；
- 每个 layout 的模板页；
- 文本 binding；
- 显式 chart/table/image slot；
- slot 容量。

Compiled Plan 记录：

- Outline 和 Manifest hash；
- Template Profile 和模板 hash；
- `asset_root`；
- 内嵌 Visualization；
- 按页排序的模板页选择；
- 完整且有序的 operation。

Compiled Renderer 不补充 Plan 中不存在的行为。

## 6. 模板现状

受版本控制的模板文件：

- `templates/financial_report_template_v1.pptx`
- `templates/template_layout_map.json`

模板为 16:9，包含 16 个参考模板页。Layout Map 当前声明 18 个逻辑 layout：

```text
cover
agenda
executive_summary
company_overview
timeline
business_structure
industry_outlook
competitive_landscape
chart_text
two_charts
capability_map
financial_review
earnings_forecast
valuation
valuation_comparison
risk_catalyst
image_only_layout
appendix
```

`template_layout_map.json` 自检结果为 18 layouts、0 warning、0 error。

模板对象定位以唯一对象名和语义锚点优先；`shape_id` 只用于当前模板的精确定位，
不能假设重新保存 PPTX 后仍保持稳定。Compiled Renderer 还会校验模板文件 SHA-256，
因此模板一旦变更，必须重新生成 Template Profile 和 Compiled Plan。

## 7. 环境、依赖与配置

### 7.1 Python

CI 覆盖 Python 3.10、3.11 和 3.12。当前机器可用的、已验证的解释器为：

```text
D:\Anaconda\python.exe
Python 3.12.3
```

仓库中的 `.venv` 指向旧用户目录下已经不存在的 Python 3.12，运行会报：

```text
No Python at "...Python312\python.exe"
```

本次盘点期间出现了未跟踪目录 `.venv-local/`，其 Python 3.12.3 可启动，但当前只安装了
`pip`，尚未安装项目依赖。不要把该目录提交到 Git；当前 `.gitignore` 只忽略 `.venv/`
和 `venv/`，并未忽略 `.venv-local/`。

建议接手者使用全新的 Python 3.12 虚拟环境，并确保旧环境不再被误用：

```powershell
python -m venv .venv-dev
.\.venv-dev\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-dev\Scripts\python.exe -m pytest -p no:cacheprovider -q
```

如果使用 `.venv-dev`，应将其加入本机 Git exclude，或后续统一更新 `.gitignore`。

### 7.2 requirements.txt

```text
python-pptx==0.6.23
jsonschema>=4.18,<5
lxml>=4.9,<7
pytest>=7,<9
httpx>=0.27,<1
PyMuPDF>=1.24,<2
```

项目没有 `pyproject.toml`、`setup.py` 或锁文件；运行时依赖仓库根目录位于
`sys.path`。依赖版本除 `python-pptx` 外多为范围约束，因此跨时间重建环境可能解析出不同版本。

### 7.3 环境变量

| 变量 | 用途 | 是否必需 |
|---|---|---|
| `MINERU_API_TOKEN` | PDF 在线解析 | 仅 `document-bundle parse` 必需 |
| `DEEPSEEK_API_KEY` | Outline 真实 LLM 调用 | 非 dry-run 必需 |
| `DEEPSEEK_MODEL` | 覆盖默认模型 | 可选 |
| `DEEPSEEK_BASE_URL` | 覆盖 OpenAI-compatible base URL | 可选 |
| `DEEPSEEK_API_PROVIDER` | `auto/deepseek/siliconflow` 请求方言 | 可选 |

代码默认模型为 `deepseek-v4-pro`，默认 base URL 为 `https://api.deepseek.com`。
SiliconFlow 模式使用精简请求体，并把 direct-planning 字符上限封顶为 60,000。

API Key 会在日志中被替换为 `***REDACTED***`，但 Outline 调用仍会把请求 URL、
请求元数据和经过清理的 payload 打印到 stdout。研报或提示词内容敏感时，应限制日志访问。

## 8. 推荐运行方式

以下命令均从仓库根目录执行。示例使用 `$PY` 变量避免混用解释器：

```powershell
$PY = ".\.venv-dev\Scripts\python.exe"
```

### 8.1 构建 Markdown DocumentBundle

```powershell
& $PY main.py document-bundle from-markdown `
  data/reports/agent/002544_2025-10-28.md `
  output/handoff/002544/document_bundle
```

### 8.2 PDF 在线解析

```powershell
$env:MINERU_API_TOKEN = "<token>"

& $PY main.py document-bundle parse `
  path/to/report.pdf `
  --output-root output/handoff
```

MinerU 默认配置：

- API：v4；
- model：`vlm`；
- language：`ch`；
- table/formula：启用；
- poll interval：2 秒；
- poll timeout：900 秒；
- request timeout：60 秒；
- transfer timeout：300 秒；
- max retries：2。

### 8.3 从现有 MinerU raw 重建

```powershell
& $PY main.py document-bundle from-raw `
  path/to/report.pdf `
  path/to/raw_directory `
  output/handoff/report/document_bundle
```

### 8.4 Outline dry-run

推荐先 dry-run，确认上下文规模、provider、selected few-shot cases 和请求结构：

```powershell
& $PY main.py generate-outline `
  output/handoff/002544/document_bundle `
  --dry-run `
  --request-output output/handoff/002544/outline_request_preview.json
```

`--request-output` 只允许与 `--dry-run` 一起使用。真实 context-compression memory
只存在于当前进程，不会写入磁盘。

### 8.5 真实生成 Outline

```powershell
$env:DEEPSEEK_API_KEY = "<api-key>"

& $PY main.py generate-outline `
  output/handoff/002544/document_bundle `
  -o output/handoff/002544/slide_outline.json
```

默认行为：

- chunk 字符预算：30,000；
- direct-planning 阈值：300,000；
- 最大输出 token：16,000；
- compression 最大 token：4,000；
- HTTP timeout：300 秒；
- 最大尝试次数：2；
- thinking：enabled；
- reasoning effort：high。

输入不超过有效 direct-planning 阈值时直接规划；否则先逐 chunk 压缩，再生成最终 Outline。
生成结果在 Schema 和 evidence 后置校验通过后才会原子替换正式输出。

### 8.6 生成 Visualization 与 Manifest

```powershell
& $PY main.py generate-visualizations `
  output/handoff/002544/slide_outline.json `
  output/handoff/002544/document_bundle `
  -o output/handoff/002544/visualizations
```

输出目录包含：

- 每个可视化一个 JSON 文件；
- `visualization_manifest.json`；
- stdout 中的 Legacy `--visualization slide_id=path` 参数提示；
- 无可追溯数据或版式不支持时的 warning/issue。

### 8.7 构建 Template Profile

Template Profile 当前没有作为正式文件提交到 `templates/`，需要从受控模板和 Layout Map 生成：

```powershell
& $PY main.py build-template-profile `
  templates/template_layout_map.json `
  templates/financial_report_template_v1.pptx `
  -o output/handoff/template_profile.json
```

### 8.8 编译 Layout Plan

```powershell
& $PY main.py compile-layout `
  output/handoff/002544/slide_outline.json `
  output/handoff/002544/visualizations/visualization_manifest.json `
  output/handoff/template_profile.json `
  -o output/handoff/002544/compiled_layout_plan.json
```

常见编译失败原因：

- Manifest 的 `outline_sha256` 与当前 Outline 不同；
- Manifest 引用了不存在的 slide；
- Profile 没有匹配某种 slide/visualization 的显式 layout 或 slot；
- required slot 没有可视化；
- 某个 Visualization 未被消费；
- 图表类型不在支持集合；
- categories/series/rows/columns 超出 slot capacity。

### 8.9 渲染 Compiled Plan

```powershell
& $PY main.py render-compiled-plan `
  output/handoff/002544/compiled_layout_plan.json `
  --template templates/financial_report_template_v1.pptx `
  -o output/handoff/002544/final.pptx
```

Renderer 会验证模板 SHA-256 和 `asset_root` 是否存在，然后复制指定模板页并顺序执行 operation。

### 8.10 Legacy Renderer 示例

```powershell
& $PY main.py render-ppt `
  examples/slide_outline_valid.json `
  --visualization slide_002=examples/visualization_valid.json `
  -o output/handoff/legacy_demo.pptx
```

如果绑定 image Visualization，还必须提供：

```text
--asset-root <DocumentBundle目录>
```

## 9. 测试与 CI

### 9.1 本地全量测试

标准命令：

```powershell
.\.venv-dev\Scripts\python.exe -m pytest -p no:cacheprovider -q
```

本次实际验证命令：

```powershell
D:\Anaconda\python.exe -m pytest -p no:cacheprovider -q
```

结果：

```text
239 passed in 15.34s
```

### 9.2 分层测试

```powershell
# 单元测试
& $PY -m pytest tests/unit -q

# DocumentBundle 专项测试
& $PY -m pytest tests/document_bundle -q

# 集成测试
& $PY -m pytest tests/integration -q

# 编译与渲染主链路
& $PY -m pytest tests/integration/test_compiled_render_pipeline.py -q

# 单个测试
& $PY -m pytest `
  tests/integration/test_compiled_render_pipeline.py::test_compiled_plan_renders_existing_chart_and_table_effect `
  -q
```

测试中的 DeepSeek 请求通过 monkeypatch 模拟；MinerU 客户端使用 `httpx.MockTransport`。
全量自动化测试不需要真实 API Token，也不会访问真实外部服务。

Renderer 集成测试会重新打开输出 PPTX，并检查页数、图表、表格和文本对象。

### 9.3 CI

`.github/workflows/ci.yml` 在 push 和 pull request 时执行：

```text
ubuntu-latest / Python 3.10
ubuntu-latest / Python 3.12
windows-latest / Python 3.11
```

CI 目前只有依赖安装和 `pytest -q`，没有：

- lint；
- formatting check；
- type check；
- coverage threshold；
- dependency/security scan；
- PPT 视觉截图回归。

## 10. 当前本地数据与产物

`data/`、`examples/` 和 `templates/` 中的受控文件可以作为开发输入。
`output/` 被 `.gitignore` 忽略，只是当前机器的实验工作区。

本地存在一份 002544 PDF DocumentBundle：

```text
output/manual-002544/document_bundle
```

其当前统计：

- 17 pages；
- 222 blocks；
- 15 sections；
- 12 tables，其中 11 complete、1 image_only；
- 8 figures；
- `validation.status=needs_review`；
- 唯一 warning 为跨页表格只有裁切图、没有完整可编辑结构。

这些数字可用于人工理解，但该目录不受版本控制，不能作为其他机器必然存在的测试夹具。

本地 `output/source_aligned/002544/` 中还有 193 页实验 Outline、20 个 Visualization 和
PPTX，但存在以下不兼容：

- 现存 Compiled Plan 声明 `schema_version=2.0.0`；
- 当前受控 Schema 只接受 `schema_version=1.0.0`；
- 现存 Plan 包含当前 Schema 不接受的 operation，例如 `add_text_box`；
- 现存 Manifest/Plan 的 `asset_root` 指向旧机器绝对路径
  `D:\HuaweiMoveData\Users\...\output\manual-002544\document_bundle`；
- 因此这些产物不能直接由当前代码可靠复现或跨机器执行。

结论：接手者应从受控输入重新生成 bundle、Manifest、Profile 和 Plan，不要修补旧 `output/`
产物来冒充当前链路通过。

## 11. 已知问题与技术债

### P0：运行环境失效

仓库 `.venv` 不可用，README 中直接调用 `.\.venv\Scripts\python.exe` 在当前机器会失败。
接手后应先重建环境，再做其他判断。

### P0：本地产物与当前 Schema 漂移

被忽略的 `output/` 中存在 Plan v2.0.0，而代码库冻结的是 Plan v1.0.0。
这会导致“文件看起来完整，但当前 loader 无法接受”的假象。

### P1：文档与实现漂移

以下现有文档仍声称 Renderer 只支持 chart/table、image 尚未实现：

- `docs/architecture/system_overview.md`
- `docs/architecture/interfaces.md`
- `docs/specs/visualization.md`

当前实现实际上已经包含 `render_image`、image slot、路径安全校验以及图片渲染测试。
后续应更新这些规范文档，避免开发者按过期边界继续工作。

历史交付文档中的 `108 passed` 和 `127 passed` 也只是当时结果，不能代表当前测试规模。

### P1：双链路并存

Legacy Layout Map Renderer 与 Compiled-plan Renderer 同时存在。兼容入口仍有价值，但新功能如果
只修改其中一条链路，容易产生行为差异。每次改动 PPT Engine 时至少要明确：

- 是否影响 Legacy `render-ppt`；
- 是否影响 Template Profile；
- 是否影响 Compiler；
- 是否影响 Compiled Renderer；
- 两条链路是否都需要测试。

### 已补齐：单命令 Pipeline 与运行清单

`python main.py run-pipeline` 已串联 bundle、outline、visualization、numeric audit、profile、
compile 和 render。运行先写入同级临时目录，全部 P0 校验通过后才发布最终目录；失败返回非零码，
且不生成或宣称生成有效 PPTX。`run_manifest.json` 保存输入、正式 Schema、Outline、
Visualization Manifest、Template Profile、模板、Compiled Layout Plan 和 PPTX 的 hash。

Pipeline 生成的 Visualization Manifest 使用相对 `asset_root` 进行阶段内校验，最终
Compiled Layout Plan 写入发布后 DocumentBundle 的明确路径，避免保留临时 staging 路径。
跨机器复制后仍需按新位置重新编译 Plan。

### P1：日志可能包含敏感研报内容

API Key 已脱敏，但 Outline 请求 payload 会打印到终端。生产环境需要日志分级、内容截断或
显式安全开关。

### P2：依赖与打包不完全可复现

没有 lockfile，也没有 Python package metadata。开发者依赖从仓库根目录运行；
依赖范围未来可能解析出不同版本。

### P2：缺少静态质量门禁

CI 仅运行测试，没有 lint、type check、coverage 和视觉回归。

### P2：当前分支和提交信息不利于追踪

`unfixedversion` 比本地 `master` 领先 1 个提交，HEAD message 为 `temple`，
无法从提交名称直接判断修改目标。仓库也没有 remote，交接时应确认真正的远端来源和目标分支。

### P2：未跟踪虚拟环境目录

`.venv-local/` 当前出现在 `git status` 中，且不在 `.gitignore`。不要误提交。

## 12. 建议的接手顺序

1. 使用 Python 3.12 创建干净环境并安装 `requirements.txt`。
2. 运行全量测试，确认仍为 239 passed 或解释合理差异。
3. 阅读 `main.py`，掌握全部 CLI 分发入口。
4. 阅读 `schemas/`，先理解数据契约，再看实现。
5. 阅读 `docs/architecture/system_overview.md` 和 `interfaces.md`，同时注意其中 image 边界已过期。
6. 阅读 `document_bundle/` 与 `document_intelligence/`，理解事实层和运行时索引边界。
7. 阅读 `outline_generator/generate_outline.py`、`llm_understanding.py` 和 `few_shot.py`。
8. 阅读 `visualization_generator/planning.py`、`generator.py`、`manifest.py`。
9. 阅读 `tools/build_template_profile.py`、`ppt_engine/compiler.py` 和 `compiled_plan.py`。
10. 阅读 `ppt_engine/renderer.py`、`slide_builder.py` 和 `visualization_renderer.py`。
11. 运行小型 compiled render 集成测试。
12. 从受控 Markdown 样例重新跑一次 dry-run 和完整确定性下游链路。
13. 最后再处理真实 API、真实 PDF 和人工 PPT 视觉验收。

## 13. 下一阶段建议

建议优先级：

1. 修复环境说明：重建 `.venv`，补充 Python 版本，并处理 `.venv-local/` ignore。
2. 同步架构文档中的 image Renderer 能力。
3. 清理或明确隔离不兼容的本地 Plan v2 产物。
4. 为推荐的新链路补充 README 完整命令。
5. 为统一 Pipeline 增加阶段缓存或显式失败恢复；当前已具备原子发布和失败清理。
6. 定义 Manifest/Plan 的可重定位策略。
7. 为模板变更增加 Profile/Plan 再生成检查。
8. 增加 lint、type check、coverage 和 PPT 视觉回归。
9. 明确 Git remote、目标分支和发布/交付流程。

## 14. 修改时必须保持的约束

- DocumentBundle 是正式事实来源；不要恢复 Parsed Document 为新主链路。
- Document Intelligence 必须保持确定性、保序、无 LLM、无持久化 memory。
- Context Compression memory 只存在于当前 Outline 生成进程。
- Slide Outline 不得包含具体图表数值、模板坐标或 `layout_id`。
- Visualization 数值和图片必须能追溯到原生 block/table/figure。
- `image_only` table 不得由 LLM 补成结构化表格。
- Template Profile 必须显式声明 slot；Renderer 不得借用其他类型区域。
- Compiled Plan 中的 Visualization 必须被恰好消费一次。
- Compiled Renderer 不得重新推断 layout 或补充 operation。
- 模板 hash 不匹配时必须失败，不得静默继续。
- 不得把 API Token 写入源码、命令历史、输出 JSON 或日志。
- 修改 Schema 时必须同步 loader、validator、样例、测试和迁移策略。

## 15. 快速验收清单

交接后可按以下项目确认环境和代码状态：

- [ ] Python 3.12 环境可用；
- [ ] `pip install -r requirements.txt` 成功；
- [ ] 全量测试通过；
- [ ] `generate-outline --dry-run` 成功；
- [ ] 小型 `render-ppt` 示例成功；
- [ ] Template Profile 构建并通过 Schema 校验；
- [ ] Manifest 能被 loader 加载；
- [ ] `compile-layout` 成功生成 Plan v1.0.0；
- [ ] `render-compiled-plan` 生成可重新打开的 PPTX；
- [ ] chart、table、image 均有相应回归验证；
- [ ] 最终 PPT 页数等于 Outline 页数；
- [ ] Git 未包含 `output/`、虚拟环境、API Key 或临时请求响应；
- [ ] 新产物没有旧机器绝对路径；
- [ ] 人工检查无文件损坏、明显重叠、裁切或文字溢出。
