# 超长网文 Novel 拆解 DAG 流程设计

> 基于 SailZen DAG Client 3.0 通用框架的网文分析流水线。

## 设计目标

1. **数据隔离**: DAG 运行时数据完全独立于 `sail_server`，仅通过 HTTP API 读取 text 结构数据
2. **超长文本支持**: 支持万章级网文的批量并行分析
3. **可扩展**: 每个分析阶段都是可替换/可扩展的节点
4. **无前端依赖**: 仅保留 SSE + HTTP API，分析结果通过接口获取

## 输入与输出

### 输入参数

```yaml
params:
  work_id: 1               # sail_server 中的作品 ID（二选一）
  edition_id: 1            # sail_server 中的版本 ID（二选一）
  sail_server_url: "http://localhost:8000"   # sail_server 地址
  batch_size: 100          # 每批分析的章节数
  max_workers: 4           # 最大并行分析组数
  analysis_types:          # 启用哪些分析维度
    - character            # 角色分析
    - plot                 # 剧情分析
    - setting              # 设定分析
    - emotion              # 情感分析
```

### 输出产物

- `work_meta.json` — 作品元数据
- `chapter_index.json` — 章节索引（含 label, title, char_count）
- `batches/` — 各批次原始文本
- `analysis/character/` — 角色分析结果
- `analysis/plot/` — 剧情分析结果
- `analysis/setting/` — 设定分析结果
- `analysis/emotion/` — 情感分析结果
- `report.json` — 综合报告

## DAG 拓扑结构

```
fetch_work_meta ─┬─→ fetch_chapter_index ──→ batch_split ─┬─→ batch_fetch_text_1 ──→ analyze_character_1
                                                              │                        analyze_plot_1
                                                              │                        analyze_setting_1
                                                              │                        analyze_emotion_1
                                                              ├─→ batch_fetch_text_2 ──→ analyze_character_2
                                                              │                        ...
                                                              ├─→ batch_fetch_text_3 ──→ ...
                                                              └─→ batch_fetch_text_N ──→ ...

all_analyses ──→ merge_character ──→ merge_plot ──→ merge_setting ──→ merge_emotion ──→ generate_report
```

### 节点说明

| 节点 | 类型 | 职责 |
|------|------|------|
| `fetch_work_meta` | `text_fetch` | 从 sail_server 获取作品/版本元数据 |
| `fetch_chapter_index` | `text_fetch` | 获取章节列表（目录） |
| `batch_split` | `python` | 按 `batch_size` 将章节分组 |
| `batch_fetch_text_N` | `text_fetch` | 批量获取第 N 组章节内容 |
| `analyze_character_N` | `skill` | 调用 LLM skill 分析角色 |
| `analyze_plot_N` | `skill` | 调用 LLM skill 分析剧情 |
| `analyze_setting_N` | `skill` | 调用 LLM skill 分析设定 |
| `analyze_emotion_N` | `skill` | 调用 LLM skill 分析情感 |
| `merge_character` | `python` | 合并各批次角色分析 |
| `merge_plot` | `python` | 合并各批次剧情分析 |
| `merge_setting` | `python` | 合并各批次设定分析 |
| `merge_emotion` | `python` | 合并各批次情感分析 |
| `generate_report` | `skill` | 生成最终综合报告 |

## 数据流与隔离策略

### 读取 sail_server（单向）

```python
# text_fetch 节点内部逻辑
async def execute(ctx):
    edition_id = ctx.params["edition_id"]
    url = f"{ctx.params['sail_server_url']}/api/v1/text/edition/{edition_id}/chapters"
    chapters = await httpx.get(url).json()
    # 只读取，不写入 sail_server
```

### DAG 独立存储

所有分析结果写入 `DAGStore`：

```
data/dag/runs/{run_id}/
├── artifacts/
│   ├── work_meta.json
│   ├── chapter_index.json
│   ├── batches/
│   │   ├── batch_000.json
│   │   ├── batch_001.json
│   │   └── ...
│   └── analysis/
│       ├── character/
│       ├── plot/
│       ├── setting/
│       └── emotion/
│   └── report.json
└── logs/
    └── *.log
```

## 动态分支机制

`batch_split` 节点执行后，根据章节数量动态生成：
- `batch_fetch_text_N` 节点：批量获取第 N 组章节内容
- `analyze_{dimension}_N` 节点：对每个分析维度（character/plot/setting/emotion）进行批次分析

```python
# batch_split 节点的返回
return NodeResult.ok(
    data={"batch_count": 5},
    next_nodes=[
        {"id": f"batch_fetch_{i}", "type": "text_fetch", "params": {...}},
        {"id": f"analyze_character_{i}", "type": "skill", "depends_on": [f"batch_fetch_{i}"], "join_to": ["merge_character"], "params": {...}},
        ...
    ]
)
```

动态节点支持以下边声明：
- `depends_on`: 该节点依赖的节点列表（创建 dependency 边）
- `join_to`: 静态汇合节点列表；动态节点完成后，这些节点才能执行

`analyze_{dimension}_N` 通过 `join_to: ["merge_{dimension}"]` 确保 `merge_{dimension}` 在**所有**对应分析节点完成后才执行，修复了 merge 节点因静态依赖 batch_split 而过早解锁的时序 bug。

## API 接口

已有通用接口足够，novel analysis 通过 `definition_id` 调用：

```bash
# 1. 创建运行（使用 novel_analysis 定义）
POST /api/v1/dag/runs
{
  "definition_id": "novel_analysis",
  "name": "斗罗大陆分析",
  "params": {
    "edition_id": 1,
    "sail_server_url": "http://localhost:8000",
    "batch_size": 100
  }
}

# 2. SSE 监听实时进度
GET /dag/sse/runs/{run_id}

# 3. 获取分析结果
GET /api/v1/dag/runs/{run_id}
# 返回包含所有节点状态，artifact 路径在 result 中

# 4. 直接读取产物（通过 store 路径）
# 产物可通过 store API 或文件系统访问
```

## 扩展性设计

### 添加新的分析维度

1. 在 `sail.yaml` 的 `node_types` 中注册新节点类型
2. 在 DAG 模板中添加对应 `analyze_{dimension}_N` 节点
3. 在 `merge_{dimension}` 节点中实现合并逻辑

### 替换分析引擎

将 `skill` 节点替换为 `python` 节点或自定义节点：

```yaml
nodes:
  - id: analyze_character_0
    type: "python"  # 或 "my_custom_analyzer"
    params:
      code: |
        # 自定义本地分析逻辑
        result = local_nlp_model.analyze(ctx.upstream["batch_fetch_0"])
```

### 调整批处理策略

修改 `batch_split` 的参数即可：

```yaml
nodes:
  - id: batch_split
    type: "python"
    params:
      batch_size: 50        # 更细的粒度
      overlap: 10           # 批次间重叠章节（上下文保留）
      strategy: "by_volume" # 或 "by_char_count"
```

## 技术债与 TODO

- [ ] text_fetch 节点需要实现 sail_server 的认证（如果需要）
- [ ] 超大文本（>100MB）需要流式读取而非全量加载
- [ ] LLM skill 调用需要实现 token 预算管理
- [ ] 分析结果需要版本化（多次运行的结果对比）
- [ ] 考虑添加增量分析（只分析新增章节）
