# FGO从者数据爬虫与Bangumi ID匹配系统

这个项目用于将Fate/Grand Order (FGO) Wiki中的从者数据与Bangumi角色ID进行匹配，并生成特定JSON格式的数据，用于下游应用。

## 功能概述

1. 从FGO Wiki获取从者数据（稀有度、职阶、宝具色卡、宝具类型、获取途径等）
2. 将从者数据与Bangumi ID进行匹配
3. 生成标准化的JSON格式数据

## 文件说明

- `fgo_scraper.py`: 主要爬虫脚本，负责处理FGO Wiki数据并与Bangumi ID匹配
- `fgo_wiki_servants.html`: FGO Wiki页面本地缓存
- `fgo_name_to_id_mapping.json`: Bangumi ID映射文件
- `fgo_output.json`: 最终生成的数据文件

## 使用方法

运行数据收集与匹配：
```
python fgo_scraper.py
```

## 匹配算法

系统使用多种匹配策略来将FGO从者与Bangumi ID匹配：

1. 直接精确匹配
2. 标准化名称匹配（处理不同的表记方式）
3. 部分匹配（处理名称一部分相同的情况）
4. 特殊情况处理（针对特定从者的自定义规则）

## 数据格式

最终生成的`fgo_output.json`文件格式如下：

```json
{
  "bangumi_id": {
    "稀有度": {
      "星级": "星级"
    },
    "职阶": {
      "职阶名称": "<img src='/assets/tag/fgo/Class/金卡职阶.png' alt='职阶名称' /> 职阶名称"
    },
    "宝具色卡": {
      "色卡": "<img src='/assets/tag/fgo/Color/色卡.png' alt='色卡' /> 色卡"
    },
    "宝具类型": {
      "类型": "类型"
    },
    "获取途径": {
      "途径": "途径"
    }
  },
  ...
}
``` 