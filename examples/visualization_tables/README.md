# Week 3 T3.5 原生表格验收样例

本目录冻结四个 Visualization JSON：

- `week3_t3_5_forecast.json`：数值对齐、空值和盈利预测；
- `week3_t3_5_valuation.json`：六列估值比较和多处空值；
- `week3_t3_5_long_labels.json`：长中文标签、列宽和换行；
- `week3_t3_5_capacity_boundary.json`：18 行 × 8 列容量边界。

生成四页人工验收 PPTX：

```powershell
python tools/build_week3_t3_5_table_acceptance.py
```

默认输出为 `output/week3_t3.5_table_acceptance.pptx`。Renderer 不会静默截断表格；超过
Layout slot 或全局 18 行 × 8 列限制时会明确失败。
