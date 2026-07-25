# Week 3 T3.4 原生图表验收样例

本目录冻结四个 Visualization JSON：

- `week3_t3_4_line.json`：多系列、空数据点跨接、预测期空心标记；
- `week3_t3_4_column.json`：分类比较、柱间距和坐标轴；
- `week3_t3_4_bar.json`：长分类标签和数值标签；
- `week3_t3_4_pie.json`：分类配色、百分比标签和图例。

生成四页人工验收 PPTX：

```powershell
python tools/build_week3_t3_4_chart_acceptance.py
```

默认输出为 `output/week3_t3.4_chart_acceptance.pptx`。该文件是视觉审核产物，不应作为
Visualization 数据事实来源。
