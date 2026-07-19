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

## 5. Demo

```powershell
python main.py validate-layout-map templates/template_layout_map.json

python main.py render-ppt `
  examples/generated/002544_2025-10-28_slide_outline.json `
  -o output/002544_outline_only_demo.pptx

python main.py render-ppt examples/slide_outline_valid.json `
  -o output/mvp_chart_table_demo.pptx `
  --visualization slide_002=examples/visualization_valid.json `
  --visualization slide_002=examples/visualization_table_valid.json
```

## 6. 验证结果

- 全量自动测试：`118 passed`。
- Layout Map validation：`VALID: 0 error(s)`。
- Outline-only Demo：11 页，可通过 python-pptx 重新打开。
- chart/table Demo：2 页，包含 1 个可编辑 chart 和 1 个可编辑 table。
- 两份 Demo 的 Shape 结构边界检查均无越界。
