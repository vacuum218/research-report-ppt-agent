# Research Report PPT Agent

将 PDF、Markdown 或纯文本研报转换为结构化 `DocumentBundle`，再生成 Slide Outline、
可视化数据和模板化 PPTX。

## 当前架构

```text
PDF ──→ MinerU / raw artifacts ──┐
                                 ├──→ DocumentBundle
Markdown / Text ─────────────────┘           ↓
                                  Document Intelligence
                                             ↓
                                  Context Compression
                                             ↓
                                     Slide Planning
                                             ↓
                              Visualization Planning
                                             ↓
                              Deterministic Visualization Generator
                                             ↓
                         Layout Resolver + PPT Renderer
                                             ↓
                                            PPTX
```

`DocumentBundle` 是唯一上游事实来源。`document_intelligence/` 只执行确定性的读取、
section/block/table/figure 索引、evidence 定位和顺序分块，不执行总结、重要性判断或 slide 规划。
Context Compression 产生的 LLM memory 仅存在于当前进程内存中，只有最终 Slide Outline 会持久化。

## 模块输入输出

| 模块 | 输入 | 输出 |
|---|---|---|
| `document_bundle/` PDF parser | PDF、MinerU API | `document_bundle/` 目录 |
| `document_bundle/` raw builder | PDF + 四个 MinerU raw 文件 | `document_bundle/` 目录 |
| `document_bundle/` Markdown builder | Markdown / plain text | `document_bundle/` 目录 |
| `document_intelligence/` | `document.json` | 只读索引、关系、evidence 与有序 chunk |
| `outline_generator/` | Document Intelligence chunk | 运行时压缩 memory → Slide Outline JSON |
| `visualization_generator/planning.py` | Slide Outline + Document Intelligence evidence | 无数值、无路径的运行时 Visualization Plan |
| `visualization_generator/generator.py` | Visualization Plan + Document Intelligence | 可追溯的 chart/table/image Visualization JSON |
| `ppt_engine/` | Slide Outline + Visualization + Layout Map + PPT 模板 | PPTX |

DocumentBundle 的正式下游接口是 `document.json` 和 `assets/`。`raw/` 与
`validation.json` 用于审计、复核和确定性重建。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PDF 在线解析需要通过环境变量配置 `MINERU_API_TOKEN`。不要把 Token 写入命令、源码或日志。

## 构建 DocumentBundle

### PDF + MinerU API

```powershell
python main.py document-bundle parse report.pdf --output-root output
```

输出位置：

```text
output/<PDF_STEM>/document_bundle/
```

### 使用已有 MinerU raw 文件重建

```powershell
python main.py document-bundle from-raw report.pdf RAW_DIRECTORY BUNDLE_DIRECTORY
```

需要的 raw 文件：

- `layout.json`
- `content_list.json`
- `model.json`
- `document.md`

### Markdown / Text

```powershell
python main.py document-bundle from-markdown report.md output/report/document_bundle
```

Markdown bundle 使用行号定位，PDF bundle 使用 `page + bbox` 定位，不会为 Markdown
伪造 PDF 坐标。

## 下游执行

Outline Generator 和 Visualization Generator 都直接读取 bundle：

```powershell
python main.py generate-outline output/report/document_bundle --dry-run

python main.py generate-visualizations `
  output/outlines/report_outline.json `
  output/report/document_bundle `
  -o output/visualizations/report

python main.py render-ppt `
  output/outlines/report_outline.json `
  -o output/report.pptx `
  --visualization slide_001=output/visualizations/report/slide_001__visual_001.json
```

`parse-report` 仍保留为旧脚本兼容入口，但其 Parsed Document JSON 不再是正式上游标准。

## DocumentBundle 目录

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

Markdown bundle 的 `raw/` 只需保留原始 `document.md`；PDF bundle 严格保留全部四个
MinerU raw 文件。

`document.json` 的冻结顶层字段：

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

正式 Schema 位于：

- `schemas/document_bundle.schema.json`
- `schemas/parsed_document.schema.json`（deprecated，仅用于旧解析器和 compat 回归）
- `schemas/slide_outline.schema.json`
- `schemas/visualization.schema.json`

## 项目结构

```text
document_bundle/          新的 PDF/Markdown 上游数据层
document_intelligence/    确定性结构索引、evidence 与 chunk
compat/structured_content/ deprecated；仅保留 DocumentBundle→Parsed Document 测试兼容
document_parser/          Markdown/plain-text 的 DocumentBundle 生产解析实现；旧 Parsed JSON CLI 兼容
outline_generator/        Context Compression + Slide Planning
visualization_generator/  视觉语义规划 + DocumentBundle 原生 chart/table/image 生成
ppt_engine/               Layout Resolver 与 PPT Renderer
ppt_template_parser/      PPT 模板结构分析
schemas/                  JSON Schema
prompts/                  Outline prompt 与 few-shot
templates/                PPT 模板和 Layout Map
tools/                    校验与模板工具
tests/                    单元、集成及回归测试
docs/                     架构、接口和交付文档
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q
```

partner 的 MinerU 客户端测试使用 `httpx.MockTransport`，不会访问真实 MinerU API。
Renderer 回归测试会重新打开生成的 PPTX 并检查页数及图表/表格对象。

详细接口见 [docs/architecture/interfaces.md](docs/architecture/interfaces.md)，
DocumentBundle 规范见 [docs/specs/document_bundle.md](docs/specs/document_bundle.md)。
