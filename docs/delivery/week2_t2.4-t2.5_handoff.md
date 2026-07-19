# Week 2 T2.4/T2.5 基础 PPT Engine 交付说明

## 1. 交付范围

本次交付完成：

- T2.4 基础 PPT Renderer。
- T2.5 固定模板 Layout Resolver 和 Layout Map validation。
- Outline-only 与可选 chart/table Visualization 的 CLI 集成。

未扩展复杂自动排版、高级溢出处理、完整图表美化或 Visualization Detector。

## 2. 模块结构

```text
ppt_engine/
├── renderer.py                # 输入校验、流程编排、PPTX 保存与重开检查
├── layout_resolver.py         # Layout Map 校验和 layout_id 选择
├── slide_builder.py           # 模板页克隆、字段适配与 Shape 填充
└── visualization_renderer.py  # 基础可编辑图表和表格
```

Renderer 复用已有 `ppt_template_parser`、模板盘点结果和
`templates/template_layout_map.json`，没有重新实现通用模板解析。

## 3. 运行时数据流

```text
Slide Outline JSON
  + optional slide_id → Visualization JSON[]
  + template_layout_map.json
  + financial_report_template_v1.pptx
            ↓
       LayoutResolver
            ↓
       slide_builder
            ↓
    visualization_renderer
            ↓
          PPTX
```

Visualization 的页面绑定属于 Renderer 编排参数，不进入冻结 Schema。

## 4. Layout 选择顺序

1. `page_role=title` 使用 `cover`。
2. 存在 table 使用 `earnings_forecast`。
3. 存在 chart 使用 `chart_text`。
4. 其余页面通过 `slide_type_defaults` 选择固定版式。
5. 未知类型降级到 `executive_summary`。

## Step 7：真实Pipeline测试（最终验收）

### 目标

验证整个系统是否能够从一份真实研报文本开始，依次完成文本结构化、Slide
Outline 生成和模板化 PPT 渲染，最终得到可人工检查的 PowerPoint 文件。

本章节定位为项目 Demo 复现指南。执行者应在仓库根目录逐步运行以下命令，
记录每一步的输入和实际输出路径，不依赖额外的自动化 Pipeline 工具。

### 输入

选择 `data/reports/` 中的一份真实 Markdown 研报。例如：

```text
data/reports/agent/002544_2025-10-28.md
```

下文使用 `xxx.md` 表示待验收研报文件：

```text
data/reports/xxx.md
```

### Step 1：研报解析

执行：

```powershell
python main.py parse-report data/reports/xxx.md
```

该命令将 Markdown 或纯文本研报转换为符合
`schemas/parsed_document.schema.json` 的 Document JSON。

未指定 `-o` 时，输出文件默认写入输入文件所在目录，文件名为：

```text
data/reports/xxx_parsed.json
```

终端会打印实际的 `Created:` 路径。记录该路径，下一步将它作为 Outline
Generator 的输入。

使用仓库真实样例时，可执行：

```powershell
python main.py parse-report data/reports/agent/002544_2025-10-28.md
```

对应输出为：

```text
data/reports/agent/002544_2025-10-28_parsed.json
```

---

### Step 2：生成 Slide Outline

首先配置 DeepSeek API Key：

```powershell
$env:DEEPSEEK_API_KEY = "<your-api-key>"
```

然后执行：

```powershell
python main.py generate-outline data/reports/xxx_parsed.json
```

输入文件是 Step 1 生成的 Document JSON。该步骤会真实调用 LLM，将 Document
JSON 转换为符合 `schemas/slide_outline.schema.json` 的 PPT 语义大纲。

未指定 `-o` 时，Outline 默认输出到：

```text
output/outlines/xxx_parsed_outline.json
```

终端会打印 `Created outline:` 和实际文件路径。建议记录该路径，并独立执行一次
Outline 校验：

```powershell
python main.py validate-outline output/outlines/xxx_parsed_outline.json
```

校验通过时应看到：

```text
VALID: 0 error(s), ... warning(s)
```

warning 用于提示内容质量问题；只有出现 error 时才表示 Outline 不能进入 PPT
渲染阶段。

使用仓库真实样例时，对应命令为：

```powershell
python main.py generate-outline `
  data/reports/agent/002544_2025-10-28_parsed.json

python main.py validate-outline `
  output/outlines/002544_2025-10-28_parsed_outline.json
```

---

### Step 3：生成 PPT

执行：

```powershell
python main.py render-ppt `
  output/outlines/xxx_parsed_outline.json `
  -o output/final_demo.pptx
```

该步骤的数据流为：

```text
Slide Outline JSON
  +
templates/template_layout_map.json
  +
templates/financial_report_template_v1.pptx
        ↓
     ppt_engine
        ↓
output/final_demo.pptx
```

Renderer 会读取 Outline 中每页的 `page_role` 和 `slide_type`，通过固定 Layout
Map 选择模板页，填充标题、核心观点、要点、来源和页码，并生成最终 PPTX。

使用仓库真实样例时，对应命令为：

```powershell
python main.py render-ppt `
  output/outlines/002544_2025-10-28_parsed_outline.json `
  -o output/final_demo.pptx
```

成功时终端应输出：

```text
Created: output/final_demo.pptx
```

---

### Step 4：人工验收

使用 Microsoft PowerPoint 打开：

```text
output/final_demo.pptx
```

逐项检查：

1. PPT 是否可以正常打开，且 PowerPoint 未提示文件损坏或需要修复。
2. PPT 页数是否等于 Outline JSON 中 `slides` 数组的元素数量。
3. 首页是否使用封面版式，公司名称、报告标题和基本信息是否正确。
4. 内容页的标题、核心观点、要点、来源和页码是否正常渲染。
5. 模板的页面比例、背景、配色、字体层级、装饰元素和页脚样式是否保留。
6. 是否存在空白页、重复页、明显对象重叠或文字溢出。

只有以上项目全部通过，才视为真实研报 Markdown → Document JSON → Slide
Outline JSON → Layout Mapping → PPTX 的完整 Demo 验收通过。
