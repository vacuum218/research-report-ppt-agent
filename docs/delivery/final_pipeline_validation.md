# Final Pipeline Validation

## Purpose

本记录用于说明 Research Report PPT Agent 的最终真实 Pipeline 验收结果。验收覆盖
真实研报解析、已验收 Slide Outline、Visualization 数据生成、语义 Layout Resolution
和最终 PPTX 渲染，不改变任何冻结接口或核心模块逻辑。

## Test Dataset

输入研报：

```text
data/reports/agent/002544_2025-10-28.md
```

该文件是一份真实上市公司研报 Markdown，用于验证段落、表格、来源信息和数值数据
能否贯穿完整生成链路。

## Pipeline

```text
002544_2025-10-28.md
        ↓
Parsed Document JSON
        ↓
Slide Outline JSON
        ↓
Visualization JSON
        ↓
Layout Resolver
        ↓
PPT Renderer
        ↓
Final PPTX
```

各阶段验收输入输出：

1. Document Parser 读取真实 Markdown，生成 Parsed Document JSON。
2. Slide Outline Generator 将 Parsed Document 转换为语义大纲。
3. Visualization Generator 使用 `visual_candidates`、`source_refs` 和原文 block
   生成符合冻结 Schema 的 Chart/Table JSON。
4. Layout Resolver 使用页面角色和业务语义选择模板 `layout_id`。
5. Renderer 将 Outline、Visualization、Layout Map 和模板组合成最终 PPTX。

## Validation Result

| 检查项 | 结果 |
|---|---:|
| Parsed Document blocks | 82 |
| Parsed Document tables | 8 |
| Slide Outline slides | 11 |
| 成功生成的 Visualization JSON | 5 |
| 最终 PPT slides | 11 |
| PPTX 是否成功生成 | 是 |
| PPTX 是否可以由 `python-pptx` 重新打开 | 是 |
| 解析 warning | 0 |
| Visualization 数据缺口 | 0 |

本次验证生成的 5 个 Visualization 分别绑定到 `slide_004`、`slide_006`、
`slide_007`、`slide_008` 和 `slide_009`。最终 PPTX 页数与 Outline 的 `slides`
数量一致。

## Verified Slides

### slide_006

```text
slide_type=industry_analysis
visual_candidates=chart
        ↓
semantic_visual_rules.industry_analysis_chart
        ↓
layout_id=industry_outlook
```

验收结果：页面实际生成 1 个 chart。

### slide_007

```text
slide_type=financial_forecast
visual_candidates=table
        ↓
semantic_visual_rules.financial_forecast_table
        ↓
layout_id=earnings_forecast
```

验收结果：页面实际生成 1 个 table。

### slide_009

```text
slide_type=valuation_analysis
visual_candidates=table
        ↓
semantic_visual_rules.valuation_analysis_comparison_table
        ↓
layout_id=valuation_comparison
```

验收结果：页面实际生成 1 个 table。

## Reproduction Commands

在仓库根目录依次执行：

```powershell
python main.py parse-report `
  data/reports/agent/002544_2025-10-28.md `
  -o output/parsed/002544_2025-10-28_parsed.json

$env:DEEPSEEK_API_KEY = "<your-api-key>"
python main.py generate-outline `
  output/parsed/002544_2025-10-28_parsed.json `
  -o output/outlines/002544_2025-10-28_slide_outline.json

python main.py generate-visualizations `
  output/outlines/002544_2025-10-28_slide_outline.json `
  output/parsed/002544_2025-10-28_parsed.json `
  -o output/visualizations

python main.py render-ppt `
  output/outlines/002544_2025-10-28_slide_outline.json `
  --visualization slide_004=output/visualizations/slide_004__visual_001.json `
  --visualization slide_006=output/visualizations/slide_006__visual_002.json `
  --visualization slide_007=output/visualizations/slide_007__visual_003.json `
  --visualization slide_008=output/visualizations/slide_008__visual_004.json `
  --visualization slide_009=output/visualizations/slide_009__visual_005.json `
  -o output/ppt/final.pptx
```

实际 Visualization 文件名和页面绑定以生成命令打印的信息或
`output/visualizations/visualization_manifest.json` 为准。

## Test Result

```text
pytest: 127 passed
```

真实研报 Pipeline 验证成功：最终 PPTX 已成功生成并重新打开，包含 11 页；
`slide_006` 的 chart、`slide_007` 和 `slide_009` 的 table 均实际存在。
