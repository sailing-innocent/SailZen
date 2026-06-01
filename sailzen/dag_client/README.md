# SailZen DAG Client 3.0

通用有向无环图（DAG）驱动智能体框架，支持自定义配置、自定义节点、自定义依赖和 OpenCode 协议原生交互。

## 核心特性

- **配置驱动**：通过 `sail.yaml` 定义 DAG 结构、节点类型和依赖关系
- **自定义节点**：内置 `skill` / `shell` / `python` 节点，支持通过 Python 类动态扩展
- **独立存储**：SQLite 数据库 + 独立文件系统，支持备份/恢复/迁移
- **SSE 实时流**：运行状态实时推送（`/dag/sse/runs/{run_id}`）
- **OpenCode 原生集成**：与 opencode 协议服务器直接交互，skill 调用即 DAG 节点
- **与 sail_server 完全解耦**：可独立运行，不依赖主服务

## 快速开始

### 1. 配置

在项目根目录创建 `sail.yaml`（或设置 `SAIL_CONFIG` 环境变量）：

```yaml
dag_client:
  name: "my_dag"
  db_path: "data/dag_client.db"
  data_dir: "data/dag"
  api_port: 9050

  opencode:
    host: "127.0.0.1"
    port: 4096

  node_types:
    - name: "skill"
      handler: "sailzen.dag_client.nodes.skill_node.SkillNode"
    - name: "shell"
      handler: "sailzen.dag_client.nodes.shell_node.ShellNode"

  required_skills:
    - "sailzen-dev-guide"

  pipelines:
    - id: "example"
      name: "示例流水线"
      nodes:
        - id: "init"
          type: "shell"
          params:
            command: "echo hello"
        - id: "analyze"
          type: "skill"
          depends_on: ["init"]
          params:
            skill: "sailzen-dev-guide"
            prompt: "分析当前项目"
```

### 2. 启动

```bash
# 使用 uv
uv run python -m sailzen.dag_client

# 指定配置
SAIL_CONFIG=./sail.yaml uv run python -m sailzen.dag_client

# 指定端口
SAIL_DAG_API_PORT=9090 uv run python -m sailzen.dag_client
```

### 3. API 调用

```bash
# 健康检查
curl http://localhost:9050/api/v1/dag/health

# 创建运行
curl -X POST http://localhost:9050/api/v1/dag/runs \
  -H "Content-Type: application/json" \
  -d '{"definition_id": "example", "name": "run_1"}'

# 订阅 SSE
curl http://localhost:9050/dag/sse/runs/{run_id}
```

## 架构

```
sailzen/dag_client/
├── config.py           # sail.yaml 配置加载
├── app.py              # Litestar HTTP 应用工厂
├── __main__.py         # 独立启动入口
├── database.py         # SQLite async 数据库
├── models.py           # SQLAlchemy ORM + Pydantic Schemas
├── repositories.py     # 数据访问层 (Repository 模式)
├── scheduler.py        # DAG 调度引擎（拓扑排序、依赖解锁）
├── executor.py         # 节点执行引擎（循环调度 + 执行）
├── events.py           # 内嵌事件总线（SSE 支持）
├── store.py            # 独立文件系统存储
├── backup.py           # 备份/恢复工具
├── opencode_bridge.py  # OpenCode 服务器桥接
├── deps.py             # 全局依赖注入
├── nodes/              # 节点类型
│   ├── base.py         # 节点执行基类
│   ├── registry.py     # 节点注册表
│   ├── skill_node.py   # OpenCode Skill 节点
│   ├── shell_node.py   # Shell 命令节点
│   └── python_node.py  # Python 代码节点
├── api/                # HTTP API
│   ├── routes.py       # REST API 路由
│   └── sse.py          # SSE 事件流路由
└── legacy/             # 旧版代码（参考用）
```

## 自定义节点

继承 `NodeExecutor` 并实现 `execute` 方法：

```python
from sailzen.dag_client.nodes.base import NodeContext, NodeExecutor, NodeResult

class MyNode(NodeExecutor):
    node_type = "my_node"

    async def execute(self, ctx: NodeContext) -> NodeResult:
        # ctx.params: 节点参数
        # ctx.upstream_results: 上游节点结果
        # ctx.opencode_client: OpenCode 客户端
        # ctx.store: 文件存储
        return NodeResult.ok(data={"result": "done"}, output="Success")
```

注册到 `sail.yaml`：

```yaml
node_types:
  - name: "my_node"
    handler: "my_module.MyNode"
```

## 数据独立性

- **数据库**：独立 SQLite 文件（`data/dag_client.db`），可整体复制迁移
- **文件系统**：独立 `data_dir`（`data/dag/`），包含 runs/artifacts/logs/backups/
- **备份**：`POST /api/v1/dag/backup` 生成 tar.gz，支持 `wipe` 恢复
- **导出**：`store.export_run(run_id)` 导出单次运行数据

## 状态机

节点状态流转：

```
PENDING -> QUEUED -> ASSIGNED -> RUNNING -> SUCCESS
                                    |
                                    +-> FAILED -> (retry) -> QUEUED
                                    |
                                    +-> BLOCKED
```

运行状态：

```
PENDING -> RUNNING -> COMPLETED
              |
              +-> FAILED
              |
              +-> CANCELLED
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `SAIL_CONFIG` | sail.yaml 路径 |
| `SAIL_DAG_DB_PATH` | 数据库路径 |
| `SAIL_DAG_DATA_DIR` | 数据目录 |
| `SAIL_DAG_API_PORT` | API 端口 |
| `SAIL_DAG_API_HOST` | API 绑定地址 |
| `SAIL_DAG_OPENCODE_HOST` | OpenCode 服务器地址 |
| `SAIL_DAG_OPENCODE_PORT` | OpenCode 服务器端口 |
| `DAG_DEBUG` | 调试模式 |

## 测试

```bash
uv run pytest tests/test_dag_client.py -v
```
