# Week 3 T3.4 原生图表能力与样式验收

- 日期：2026-07-25
- 实现状态：**已完成**
- 自动测试：**已通过**
- 视觉审核：**已通过**
- 执行状态：**T3.4 正式完成**

## 实现范围

`ppt_engine/visualization_renderer.py` 已为 PowerPoint 原生 Chart 补齐：

- `line`：固定线宽和圆形标记，预测期使用空心标记；
- `column`：固定系列色、柱间距、坐标轴和浅色网格线；
- `bar`：在 column 样式基础上默认显示数值标签；
- `pie`：按分类循环配色、底部图例和百分比标签；
- 公共字体、轴、图例、数据标签和 number format 样式；
- 非法颜色、图例位置、pie 数据及 secondary axis 的明确错误。

## 数据真实性修复

此前 `_chart_data()` 会把 `null` 替换成 `0`。当前版本直接把 `None` 交给项目固定的
`python-pptx==0.6.23`，使缓存和内嵌工作簿保留空数据点，不再把缺失证据伪装成零。line 的
`c:dispBlanksAs` 设置为 `span`：缺失位置没有数值和 marker，但相邻已知点之间保持连续线段。

## 自动验收

新增 `tests/unit/test_visualization_renderer.py`，覆盖：

- line/column/bar/pie 类型和 PPTX 重新打开；
- 图例、系列数、系列色、网格线、柱间距和数据标签；
- `null` 在 chart cache 中不产生零值；
- 预测期点标记；
- pie 对多系列、缺失值和负值的拒绝；
- 四份固定 JSON 的 Schema 校验。

固定样例位于 `examples/visualization_charts/`。生成验收 Deck：

```powershell
python tools/build_week3_t3_4_chart_acceptance.py
```

默认产物：

```text
output/week3_t3.4_chart_acceptance.pptx
```

## 自动测试结果

断线修复前的结果：

- `tests/unit/test_visualization_renderer.py`：10 passed；
- `tests/unit/test_ppt_engine.py` +
  `tests/integration/test_template_profile.py`：15 passed；
- 完整回归：316 passed；
- 验收 Deck：已成功生成 4 个原生图表样例。

断线修复新增了 `c:dispBlanksAs=span` 断言。用户重新运行测试和验收 Deck 后确认问题已经解决。

执行命令：

```powershell
python -m pytest tests/unit/test_visualization_renderer.py -q
python -m pytest tests/unit/test_ppt_engine.py tests/integration/test_template_profile.py -q
python -m pytest -q
python tools/build_week3_t3_4_chart_acceptance.py
```

## 视觉审核结果

用户已打开 `output/week3_t3.4_chart_acceptance.pptx` 并完成逐页检查：

1. 字体、配色和图例是否一致；
2. line 的缺失位置是否没有 marker/数值但线段连续，预测期是否为空心点；
3. column/bar 标签是否拥挤或截断；
4. pie 百分比和分类颜色是否易读；
5. 右键图表后能否使用 PowerPoint 的“编辑数据”。

四类图表均通过视觉审核；line 的空数据点不再造成线段中断，同时未产生伪造数值。T3.4
正式完成。
