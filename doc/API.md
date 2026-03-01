# SailServer API接口文档


### 人物检测 API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/analysis/character-detection/` | 创建检测任务 |
| POST | `/api/v1/analysis/character-detection/preview` | 预览检测 |
| POST | `/api/v1/analysis/character-detection/task/{id}/save` | 保存结果 |
| GET | `/api/v1/analysis/character-detection/deduplicate/{id}` | 获取去重候选 |
| POST | `/api/v1/analysis/character-detection/merge` | 合并人物 |
| POST | `/api/v1/analysis/character-detection/batch-import` | 批量导入 |


### 设定提取 API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/analysis/setting-extraction/` | 创建提取任务 |
| POST | `/api/v1/analysis/setting-extraction/preview` | 预览提取 |
| POST | `/api/v1/analysis/setting-extraction/task/{id}/save` | 保存结果 |
| GET | `/api/v1/analysis/setting-extraction/relations/{id}` | 获取关系图数据 |
| POST | `/api/v1/analysis/setting-extraction/relations` | 创建设定关系 |