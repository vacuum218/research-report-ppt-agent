# 当前项目代码交付说明

## 1. 当前完成情况

项目目前已经完成研报解析、大纲生成、大纲校验、PPT 模板解析和 Layout Map
构建能力。Visualization Detector 和 PPT Renderer 尚未实现。

```text
研报 Markdown/TXT
    ↓ document_parser
Parsed Document
    ↓ outline_generator
Slide Outline
    ↓ 后续待实现
Visualization → Layout Mapping → PPT Renderer
```

Week 2 的 T2.1、T2.2、T2.3 已通过验收。当前全量测试结果为
`108 passed`。

## 2. 主要代码文件

### 2.1 统一命令入口

| 文件 | 功能 |
|---|---|
| `main.py` | 项目统一命令入口，注册解析、生成、校验和模板处理子命令 |

常用命令：

```powershell
python main.py --help
python main.py parse-report <report.md> -o <parsed.json>
python main.py generate-outline <parsed.json> -o <outline.json>
python main.py validate-outline <outline.json>
```

### 2.2 研报解析

| 文件 | 功能 |
|---|---|
| `document_parser/parse_report.py` | 将 Markdown 或纯文本研报解析为结构化 Parsed Document |
| `document_parser/__init__.py` | 对外暴露解析器接口 |

`parse_report.py` 当前支持：

- Markdown 和纯文本标题；
- 段落、列表、引用和代码块；
- Markdown 表格和图片；
- 原文行号、章节路径、block ID 和引用信息；
- 输出前的数据完整性检查。

主要调用接口：

```python
from pathlib import Path

from document_parser import parse_file

document = parse_file(Path("report.md"))
```

输出必须符合：

```text
schemas/parsed_document.schema.json
```

### 2.3 Slide Outline 生成

| 文件 | 功能 |
|---|---|
| `outline_generator/generate_outline.py` | 构造 Prompt、调用 DeepSeek、解析 JSON、校验结果并执行纠错重试 |
| `outline_generator/__init__.py` | 对外暴露大纲生成接口 |
| `prompts/outline_system_prompt.md` | 大纲生成的系统提示词 |
| `prompts/outline_few_shot_examples.json` | 大纲生成 Few-shot 示例 |

`generate_outline.py` 当前负责：

- 校验输入 Parsed Document；
- 根据输入长度选择研报 blocks；
- 构造 DeepSeek 请求；
- 使用 thinking mode 和 JSON Output；
- 处理空响应、截断、非法 JSON 和 HTTP 错误；
- 对可恢复错误进行纠错重试；
- 校验 Schema、source 引用和 ID；
- 仅在校验通过后保存正式大纲。

运行真实生成前，需要配置：

```powershell
$env:DEEPSEEK_API_KEY = "<your-key>"
```

输出必须符合：

```text
schemas/slide_outline.schema.json
```

### 2.4 Outline 与 Visualization 校验

| 文件 | 功能 |
|---|---|
| `tools/validate_outline.py` | 校验 Slide Outline 的 JSON Schema、重复 ID 和来源引用 |
| `tools/validate_visualization.py` | 校验 Visualization JSON 的 Schema 和语义约束 |

示例：

```powershell
python main.py validate-outline examples/slide_outline_valid.json
python main.py validate-visualization examples/visualization_valid.json
```

权威接口文件：

| Schema | 用途 |
|---|---|
| `schemas/parsed_document.schema.json` | 研报解析结果 |
| `schemas/slide_outline.schema.json` | 幻灯片语义大纲 |
| `schemas/visualization.schema.json` | 图表和表格数据 |

其中 `slide_outline.schema.json` 和 `visualization.schema.json` 以本仓库版本为准，
合并代码时不要被其他项目中的同名 Schema 覆盖。

### 2.5 PPT 模板解析

| 文件 | 功能 |
|---|---|
| `ppt_template_parser/ppt_template_parser.py` | 通用 PPTX 结构解析，读取页面尺寸、母版、布局、幻灯片和 shape |
| `ppt_template_parser/style_parser.py` | 解析 shape 的填充、边框和文字样式 |
| `ppt_template_parser/theme_parser.py` | 从 PPTX theme XML 中解析主题颜色和字体 |
| `ppt_template_parser/__init__.py` | 对外暴露模板解析器 |

这部分提供通用模板解析能力，适合分析任意 PPTX 的内部结构。

### 2.6 模板盘点与 Layout Map

| 文件 | 功能 |
|---|---|
| `tools/inspect_template.py` | 盘点模板中每页的 shape、placeholder、图表、表格及坐标 |
| `tools/build_layout_map.py` | 根据模板盘点结果建立语义字段到模板对象的映射 |
| `templates/template_layout_map.json` | 当前模板的预生成 Layout Map |

`ppt_template_parser/` 与这里的区别：

- `ppt_template_parser/` 负责通用 PPTX 结构和样式解析；
- `inspect_template.py` 负责生成便于 Layout Map 使用的对象清单；
- `build_layout_map.py` 负责把标题、正文、图表槽位等语义字段映射到具体对象。

当前 Layout Map 是 Renderer 的上游输入，但 Renderer 尚未实现。

## 3. 测试代码

| 文件 | 覆盖范围 |
|---|---|
| `tests/unit/test_report_parser.py` | Markdown/纯文本解析器 |
| `tests/unit/test_outline_generator.py` | DeepSeek 响应、错误处理、校验和重试 |
| `tests/unit/test_outline_schema.py` | Slide Outline Schema |
| `tests/unit/test_visualization_schema.py` | Visualization Schema |
| `tests/unit/test_main_entrypoint.py` | `main.py` 命令入口 |
| `tests/integration/test_pipeline.py` | 解析、生成和校验流程 |
| `tests/integration/test_module_entrypoints.py` | 四个功能模块的导入和脚本入口 |
| `tests/integration/test_repository_contracts.py` | Schema、Prompt、文档和目录一致性 |
| `tests/fixtures/` | 解析器使用的 Markdown/TXT 测试素材 |

运行测试：

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

## 4. 样例与数据

| 路径 | 内容 |
|---|---|
| `examples/slide_outline_valid.json` | 合法 Slide Outline 示例 |
| `examples/visualization_valid.json` | 合法 Visualization 示例 |
| `examples/generated/002544_2025-10-28_slide_outline.json` | DeepSeek 真实生成并通过人工验收的大纲 |
| `data/reports/agent/` | Agent 生成或整理的研报样例 |
| `data/reports/human/` | 人工研报样例 |
| `data/references/` | 项目参考资料 |
| `templates/` | PPT 模板和 Layout Map |

正式验收样例：

```text
输入：
data/reports/agent/002544_2025-10-28.md

输出：
examples/generated/002544_2025-10-28_slide_outline.json

结果：
11 slides，0 error，0 warning
```

逐页人工检查记录位于：

```text
docs/reviews/T2.3_002544_outline_review.md
```

## 5. Partner 建议阅读顺序

建议按以下顺序快速理解项目：

1. `README.md`：了解安装和命令；
2. `main.py`：了解当前可以执行的功能；
3. `schemas/`：了解三个阶段的数据接口；
4. `document_parser/parse_report.py`：了解研报如何转成 blocks；
5. `outline_generator/generate_outline.py`：了解 LLM 生成和校验链路；
6. `tools/validate_outline.py`：了解 Outline 的语义约束；
7. `ppt_template_parser/` 和 `tools/inspect_template.py`：了解模板解析；
8. `tools/build_layout_map.py`：了解模板字段映射；
9. `tests/`：通过测试了解各模块的预期行为。

## 6. 尚未实现

当前不要在仓库中寻找以下运行时模块，它们还处于规划阶段：

- Visualization Detector：从 Outline 和原文提取图表、表格数据；
- Layout Selector：根据页面语义选择合适的 Layout；
- PPT Renderer：将内容、Visualization 和 Layout Map 写入 PPTX；
- 端到端研报到 PPT 的完整生成流程。

后续开发应保持以下职责边界：

```text
Slide Outline：每页讲什么
Visualization：展示哪些数据
Layout Mapping：内容放到模板哪里
Renderer：如何生成最终 PPT 对象
```
