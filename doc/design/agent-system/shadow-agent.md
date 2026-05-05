# Shadow Agent — 24h 自动化笔记助手设计

> **目标**：让 SailZen 成为一个真正的"影子助手"，运行在服务器和开发机上，永不休眠。自动同步知识库、发现补全任务、生成 patch，并通过 CLI 与 AI 交互。

---

## 1. 架构概览

Agent Daemon (Python) 一个Agent级别的守护线程，用来开启worker和scheduler
- 同步vault
- 开启note分析
- 任务运行
- 生成Patch

然后这些子目录发出的任务封装为Job统一走Job Scheduler，存入State Store
最终与三个功能交互
- Github Vault (git clone/branch/push)
- Dendron Engine Server (via express)
- SailServer (via litestar python)

[arch](./shadow_agent_arch.excalidraw.png)

## 2. 核心组件

### 2.1 Agent Daemon (`sail_server/agent/daemon.py`)

主控进程，负责：
- 加载配置，初始化各 Worker
- 启动 HTTP 管理接口（供 CLI 查询状态、触发任务）
- 注册系统信号处理（优雅退出）
- 维护进程心跳

```python
class AgentDaemon:
    def __init__(self, config: AgentConfig):
        self.scheduler = JobScheduler()
        self.vault_sync = VaultSyncWorker(config.vaults)
        self.analyzer = NoteAnalyzerWorker(config.analysis)
        self.patch_gen = PatchGeneratorWorker(config.git)
        self.api = AgentAdminAPI(self)  # FastAPI/Litestar 子应用

    async def start(self):
        # 1. 恢复未完成的任务
        await self._recover_jobs()
        # 2. 注册定时任务
        self.scheduler.add_interval(self.vault_sync.sync_all, minutes=30)
        self.scheduler.add_interval(self.analyzer.scan_and_create_tasks, minutes=60)
        # 3. 启动管理 API
        await self.api.start()
        # 4. 主循环
        await self._main_loop()
```

### 2.2 Vault Sync Worker (`sail_server/agent/vault_sync.py`)

自动同步远端 vault：
- 支持 GitHub/GitLab 仓库（SSH/HTTPS）
- 支持多 vault 配置
- 检测到更新后触发 `NoteAnalyzer`

```python
class VaultSyncWorker:
    async def sync_all(self):
        for vault in self.config.vaults:
            if await self._has_remote_update(vault):
                await self._pull_and_merge(vault)
                await self._notify_analyzer(vault)

    async def _pull_and_merge(self, vault: VaultConfig):
        # 使用 git pull --rebase 或 git fetch + merge
        # 冲突时生成 conflict report 到任务系统，不阻塞
```

### 2.3 Note Analyzer (`sail_server/agent/note_analyzer.py`)

连接 Dendron Engine Server，分析笔记库状态：
- **TODO 提取**：扫描 `#task` / `- [ ]` / `[[todo]]` 等标记
- **链接补全**：发现 `[[不存在的链接]]`，更新迁移或者是构建
- **Schema 漂移**：笔记层级与 schema 定义不匹配

分析结果写入 `agent_jobs` 表，状态为 `pending_review`。

```python
class NoteAnalyzerWorker:
    async def scan_and_create_tasks(self):
        engine = DendronEngineClient.discover(self.ws_root)
        notes = await engine.query_notes(qs="*")

        tasks = []
        tasks.extend(self._find_orphans(notes))
        tasks.extend(self._find_missing_dailies(notes))
        tasks.extend(self._find_todos(notes))
        tasks.extend(self._find_broken_links(notes))

        for t in tasks:
            await self._create_agent_job(t)
```

### 2.4 Task Runner Worker (`sail_server/agent/task_runner.py`)

- 读取 `agent_jobs` 中 `auto_approved=True` 的任务
- 调用 engine-server API 执行笔记修改
- 记录变更日志

支持的任务类型：


### 2.5 Patch Generator (`sail_server/agent/patch_generator.py`)

自动执行 `finalize-today-work` 的逻辑：
- 检测当前分支是否有 ahead of origin 的 commit
- 自动生成命名规范的 patch 文件到 `patches/`
- 验证 patch 可应用性
- 清理已确认 push 的旧 patch

```python
class PatchGeneratorWorker:
    async def generate_patches(self, branch: str = None):
        branch = branch or await self._get_current_branch()
        ahead = await self._commits_ahead_of_origin(branch)
        if not ahead:
            return

        topic = await self._infer_topic(ahead)  # 用 LLM 或规则推断主题
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"patches/{date_str}-sailzen-{topic}.patch"

        await self._run_git_format_patch(branch, filename)
        await self._verify_patch(filename)
        await self._record_patch_job(filename, ahead)
```

### 2.6 Job Scheduler (`sail_server/agent/job_scheduler.py`)

基于 APScheduler 的轻量调度器：
- `interval`：定期轮询（vault sync、analyzer）
- `cron`：定时任务（每日 23:00 自动生成 patch）
- `event`：事件触发（vault 更新后立刻分析）

---

## 3. 数据模型

### 3.1 Agent Job 表（新增）

```sql
CREATE TABLE agent_jobs (
    id              SERIAL PRIMARY KEY,
    job_type        VARCHAR(64) NOT NULL,      -- vault_sync / note_analysis / patch_gen / task_exec
    status          VARCHAR(32) DEFAULT 'pending', -- pending / running / completed / failed / pending_review
    params          JSONB DEFAULT '{}',
    result          JSONB DEFAULT NULL,
    error_message   TEXT,
    auto_approved   BOOLEAN DEFAULT FALSE,     -- 是否可无人值守执行
    created_by      VARCHAR(32) DEFAULT 'system', -- system / user / ai
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    ctime           TIMESTAMP DEFAULT NOW(),
    mtime           TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_jobs_status ON agent_jobs(status);
CREATE INDEX idx_agent_jobs_type ON agent_jobs(job_type);
```

### 3.2 Agent Config 表（新增，可选）

```sql
CREATE TABLE agent_configs (
    key   VARCHAR(128) PRIMARY KEY,
    value JSONB NOT NULL,
    mtime TIMESTAMP DEFAULT NOW()
);
```

---

## 4. CLI 工具链 (`sailzen-agent`)

### 4.1 安装与入口

```bash
# 注册为 uv script 或独立 CLI
uv run cli/agent.py --help

# 或打包后
sailzen-agent --help
```

### 4.2 命令参考

```bash
# ── 生命周期 ──
sailzen-agent start          # 一键启动 Daemon（后台）
sailzen-agent start --fg     # 前台运行（调试用）
sailzen-agent stop           # 优雅停止
sailzen-agent status         # 查看 Daemon 状态、运行时长
sailzen-agent restart        # 重启

# ── Vault 管理 ──
sailzen-agent vault list                    # 列出已配置的 vaults
sailzen-agent vault sync [vault-name]       # 手动触发同步
sailzen-agent vault add <name> <git-url>    # 添加新 vault

# ── 任务管理 ──
sailzen-agent task list                     # 查看待处理任务
sailzen-agent task run <job-id>             # 手动执行任务
sailzen-agent task approve <job-id>         # 批准 pending_review 任务
sailzen-agent task skip <job-id>            # 跳过任务

# ── 笔记分析 ──
sailzen-agent analyze now                   # 立即执行全库分析
sailzen-agent analyze orphans               # 仅分析孤儿笔记
sailzen-agent analyze dailies               # 检查缺失的 daily
sailzen-agent analyze todos                 # 扫描 TODO 项

# ── Patch 管理 ──
sailzen-agent patch gen                     # 立即生成 patch
sailzen-agent patch list                    # 列出已生成的 patches
sailzen-agent patch verify <file>           # 验证 patch

# ── AI 交互接口 ──
sailzen-agent ai query "找出所有关于 AI Agent 的笔记"
sailzen-agent ai exec "为 [[daily.journal.2024.01.01]] 创建缺失的下一天"
sailzen-agent ai report                   # 生成今日工作摘要
```

### 4.3 一键启动脚本

```bash
#!/bin/bash
# scripts/start-shadow-agent.sh

# 1. 检查 Sail Server 是否运行
if ! curl -s http://localhost:1974/health > /dev/null; then
    echo "[Agent] Starting Sail Server..."
    uv run server.py --dev &
    sleep 3
fi

# 2. 检查 Engine Server 是否可发现
if [ ! -f "${VAULT_PATH}/.dendron.port" ]; then
    echo "[Agent] Warning: Engine Server port not found. VSCode plugin may not be active."
    echo "[Agent] Shadow Agent will use file-system fallback mode."
fi

# 3. 启动 Agent Daemon
exec uv run cli/agent.py start "$@"
```

---

## 5. AI 交互设计

### 5.1 设计原则

Agent 不是替代用户做决策，而是：
- **发现**需要用户关注的事情
- **建议**可执行的操作
- **自动**执行低风险、高确定性的任务
- **汇报**执行结果，等待反馈

### 5.2 AI 可调用接口

通过 `sailzen-agent ai <subcmd>` 暴露结构化接口，AI 可以通过 shell 调用，也可以通过 MCP (Model Context Protocol) 直接连接。

**示例交互流：**

```
AI: sailzen-agent ai query "最近三天我写了什么笔记？"
Agent: [调用 engine query，返回摘要]

AI: sailzen-agent ai exec "为缺失的 daily journal 生成模板"
Agent: [创建 agent_jobs，状态 pending_review]

AI: sailzen-agent task approve 42
Agent: [执行 job 42，创建 daily note，返回结果]

AI: sailzen-agent ai report
Agent: [生成 Markdown 报告]
```

### 5.3 MCP Server 模式（可选扩展）

暴露 MCP Server，让支持 MCP 的 AI 客户端直接连接：

```python
# sail_server/agent/mcp_server.py
# 提供 tools: query_notes, create_note, update_note, list_tasks, generate_patch
```

---

## 6. 与现有系统的集成

| 现有系统 | 集成方式 | 说明 |
|---------|---------|------|
| **Sail Server** (Litestar) | HTTP Client | Agent 调用 `/api/v1/*` 读写项目/任务/文本数据 |
| **Engine Server** (Express) | HTTP Client | 通过 `dendron_kb.py` 同类客户端访问笔记 CRUD |
| **DAG Pipeline** | 复用 `dag_executor.py` | 复杂分析任务走 DAG，支持 SSE 进度 |
| **Task Scheduler** | 复用 `AnalysisTaskRunner` | LLM 驱动的文本分析任务 |
| **Bot/Watcher** | 并行运行 | Agent Daemon 与 Feishu Bot 可共存，Bot 可转发指令给 Agent |
---

## 7. 配置示例 (`agent.yaml`)

```yaml
agent:
  name: "home-shadow-agent"
  data_dir: "./data/agent"
  log_level: INFO

  admin_api:
    host: "127.0.0.1"
    port: 1975
    auth_token: "${AGENT_API_TOKEN}"  # 环境变量注入

  scheduler:
    timezone: "Asia/Shanghai"

  vaults:
    - name: "main-notes"
      url: "git@github.com:username/main-notes.git"
      local_path: "./vaults/main-notes"
      branch: "main"
      sync_interval_minutes: 30
      engine_port_file: "./vaults/main-notes/.dendron.port"

    - name: "work-notes"
      url: "git@github.com:company/work-notes.git"
      local_path: "./vaults/work-notes"
      branch: "ai"
      sync_interval_minutes: 60

  analysis:
    enabled: true
    scan_interval_minutes: 60
    rules:
      orphan_detection: true
      daily_gap_detection: true
      todo_extraction: true
      broken_link_detection: true
      schema_drift_detection: false  # 实验性功能

  patch:
    enabled: true
    cron: "0 23 * * *"  # 每天 23:00
    output_dir: "./patches"
    auto_generate_topic: true  # 用 LLM 推断主题

  llm:
    provider: "moonshot"
    model: "kimi-k2.5"
    temperature: 0.3  # 低温度，确定性任务
```

---

## 8. 部署模式

### 8.1 开发机模式（推荐起步）

```bash
# 与 VSCode 共存
# Engine Server 由 VSCode 插件启动
# Agent Daemon 独立启动，连接 VSCode 启动的 Engine
sailzen-agent start --fg
```

### 8.2 服务器模式（24h 运行）

```bash
# 服务器无 VSCode，需要 headless 的 Engine Server
# 方案 A：用 api-server 独立启动 Engine（需评估）
# 方案 B：Agent 直接操作文件系统，绕过 Engine（降级模式）

# 使用 systemd / supervisor 托管
sailzen-agent start
```

### 8.3 混合模式

开发机运行完整 Agent，服务器仅运行 `Vault Sync + Patch Gen`，通过 API 上报状态。

---

## 9. 安全与约束

1. **禁止自动 push**：Agent 只生成 patch，不执行 `git push origin`
2. **确认门**：高风险任务（删除、重命名、跨 vault 移动）必须 `pending_review`
3. **LLM 成本限制**：自动执行的 LLM 调用设 token 上限和成本告警
4. **Git 冲突处理**：pull 冲突时暂停自动 sync，上报任务等待人工解决
5. **API Token**：Admin API 必须配置 `auth_token`，防止未授权访问

---

## 10. 演进路线

| 阶段 | 功能 | 周期 |
|------|------|------|
| **MVP** | Vault Sync + Daily 检测 + Patch Auto-gen + CLI | 1 周 |
| **v0.2** | TODO 提取 + Stub 自动创建 + Orphan 报告 | 1 周 |
| **v0.3** | DAG Pipeline 集成（大纲提取、分析任务自动触发） | 2 周 |
| **v0.4** | MCP Server + AI 自然语言交互 | 2 周 |
| **v1.0** | 多 Agent 协作、分布式任务、智能任务优先级排序 | 1 月 |

---

## 11. 附录：关键代码位置

| 文件 | 用途 |
|------|------|
| `sail_server/agent/daemon.py` | Agent 主控 |
| `sail_server/agent/vault_sync.py` | Vault 同步 |
| `sail_server/agent/note_analyzer.py` | 笔记分析 |
| `sail_server/agent/patch_generator.py` | Patch 生成 |
| `sail_server/agent/job_scheduler.py` | 作业调度 |
| `cli/agent.py` | CLI 入口 |
| `sail_server/infrastructure/orm/agent.py` | Agent ORM 模型 |

