# 接口规范与开发规则

## Slide Outline JSON

用于连接：

文本解析模块

和

PPT生成模块。

推荐结构：

``` json
{
  "slides": [
    {
      "title": "",
      "summary": [],
      "source_text": "",
      "visual_candidates": []
    }
  ]
}
```

## Visualization JSON

推荐结构：

``` json
{
  "type": "line",
  "title": "",
  "unit": "",
  "categories": [],
  "values": [],
  "source": ""
}
```

## 开发规则

1.  所有模块必须独立
2.  输入输出必须明确
3.  修改 schema 必须同步文档
4.  新功能必须增加测试
5.  不允许直接修改核心接口导致联调失败

## Codex 工作方式

每次启动：

第一步： 阅读 docs/

第二步： 确认当前任务属于哪个模块

第三步： 查看已有代码

第四步： 修改并测试

第五步： 更新文档
