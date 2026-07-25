# Week 3 T3.5 原生表格样式与容量验收

- 日期：2026-07-25
- 实现状态：**代码修改完成**
- 自动测试：**等待用户手动运行**
- 视觉审核：**等待生成验收 Deck**

## 实现范围

`ppt_engine/visualization_renderer.py` 已为 PowerPoint 原生 Table 补齐：

- 深色表头、白色粗体文字、浅色隔行底纹和统一细边框；
- 表头及所有数据单元格统一水平居中；
- 首列默认加粗，所有单元格垂直居中并启用换行；
- 根据中英文显示宽度和数值列类型确定性分配列宽；
- 表头及数据行使用稳定行高，内容少时不强行拉满整个 slot；
- `null` 保持为空单元格；
- 全局 18 数据行 × 8 列容量上限。

## 容量和溢出策略

Compiler 继续优先应用 Layout slot 的 `max_rows/max_columns`。若精确模板容纳不了，会尝试合法的
adaptive layout；若所有可用 slot 均超限则明确失败。Renderer 另设 18 × 8 全局安全上限。

当前策略是 `error`：

- 不截断 rows；
- 不截断 columns；
- 不自动缩写单元格内容；
- 不在 Renderer 中自动拆页；
- 错误信息提示改用更大 slot 或 continuation page。

自动表格分页不属于 T3.5，将在确有需求时作为独立任务实现。

## 自动验收

新增 `tests/unit/test_table_renderer.py`，覆盖：

- PPTX 保存后重新打开；
- 表头、隔行底纹、字体、边框和垂直对齐；
- 文本、数值和百分比对齐；
- `null` 空单元格；
- 列宽总和、首列权重和稳定行高；
- 19 行、9 列及不规则 rows 的明确拒绝；
- 四份固定样例的 Visualization Schema 校验。

`tests/unit/test_layout_compiler.py` 增加所有可用 slot 均无法容纳超大表格时的失败测试。

## 固定样例与验收 Deck

样例位于 `examples/visualization_tables/`：

1. 盈利预测；
2. 可比公司估值；
3. 长中文标签；
4. 18 行 × 8 列容量边界。

生成四页验收 Deck：

```powershell
python tools/build_week3_t3_5_table_acceptance.py
```

默认输出：

```text
output/week3_t3.5_table_acceptance.pptx
```

## 用户手动执行

```powershell
python -m pytest tests/unit/test_table_renderer.py -q
python -m pytest tests/unit/test_layout_compiler.py tests/unit/test_ppt_engine.py tests/integration/test_template_profile.py -q
python -m pytest -q
python tools/build_week3_t3_5_table_acceptance.py
```

打开验收 Deck 后检查：

1. 表头、字体、边框和隔行底纹是否一致；
2. 文本和数值对齐是否正确；
3. 前三页列宽是否合理、长中文是否可读；
4. 空单元格是否为空而不是 0；
5. 第四页 18 × 8 边界表格是否仍可读且没有截断；
6. 表格是否仍是可编辑的 PowerPoint 原生对象。

测试和人工视觉审核通过后，T3.5 才能标记为正式完成。
