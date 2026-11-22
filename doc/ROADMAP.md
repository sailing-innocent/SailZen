# SailZen 开发路线图与迭代规划（Roadmap）

> **版本**: v3.0-plan | **更新**: 2026-11-22 | **状态**: 🔄 活跃执行基线
> **关联文档**: [SailZen3.0.md](./SailZen3.0.md) · [AGENTS.md](../AGENTS.md) · [maintain/DevOps.md](./maintain/DevOps.md) · [design/overview.md](./design/overview.md)

---

## 1. 长期愿景与产品收敛

SailZen 历经从笔记插件（Dendron Fork）→ Web + Python 后端 → Android 随身端 → 24/7 AI 代理（SailTick）的演进，如今进入 **SailZen 3.0 实战整合期**。

### 三条不变的架构原则

1. **云端结构化数据中枢**：公网 Linux 云服务器运行 `PostgreSQL + sail_server + sailtick`，作为个人结构化数据（财务、健康、节奏、物资、提醒、票据）的**唯一权威事实源**。
2. **端侧分工明确，不重复造轮子**：
   - **Web (`site/`)**：桌面管理、批量编辑、深度可视化与系统配置。
   - **Android (`android/`)**：随身哨兵——系统级被动触达、3 秒现场采集与离线队列（**已正式替代废弃的飞书机器人**）。
   - **VSCode 插件 (`packages/vscode_plugin/`)**：基于 Dendron 的层级 Markdown 笔记工作台，保持本地优先与 Git 同步。
   - **AI Agent (`sailtick/` + `sailzen-cli`)**：**Notes are notes. Databases are databases. The Agent is the bridge, not the replacement.**
3. **人做规划与验收，AI 做本地迭代与自动运维**：用自动化运维底座消除“手工备份、手工建库、手工 SSH 发布”的摩擦，让版本迭代进入高速正循环。

---

## 2. 当前项目盘点与即时技术债（2026-11-22 审计）

在开启下一阶段功能开发前，本次梳理发现了以下必须先清零的**高优技术债**：

| 优先级 | 问题项 | 位置 | 说明与处理方式 |
|---|---|---|---|
| **P0** | **`health_router` 未挂载回归** | `server.py` | Commit `e4cc03f` 中 `health_router` 被误从 `self.api_router` 列表移除（导致 `/api/v1/health/*` 路由不可达），需立即恢复并补充冒烟测试防止回归 |
| **P0** | **本地/云端运维自动化缺口** | `scripts/ops/`（待建） | 补齐云端 `pg_dump` 备份、本地调试 PG 一键还原、SSH 自动化部署与健康检查回滚脚本（详见 [DevOps.md](./maintain/DevOps.md)） |
| **P1** | **systemd 服务命名与路径不一致** | `scripts/sailtick.service` vs `doc/maintain/DeployPostgres.md` | 统一为 `scripts/sailzen-server.service` + `.env.ops` 参数化配置 |
| **P1** | **`db_sync.py` 缺失新模块 ORM** | `scripts/db_sync.py` | 补齐 `reminder`、`rhythm`、`tick` ORM 导入（仅用于轻量 SQLite 导出；PG 间同步以原生 `pg_dump`/`pg_restore` 为主） |
| **P1** | **废弃飞书支线清理收口** | `sail_bot/`、`bot.py`、`bot_watcher.py`、`sail/feishu_card_kit/` | 文档已标明停用；择机整体归档至 `archive/lark_bot/` 并从 `pyproject.toml` 评估移除 `lark-oapi` 依赖 |
| **P2** | **历史遗留模块瘦身** | `packages/dendron_plugin_views/`、`scripts/agent-daemon.service` | 清理或归档不再使用的旧 views 与已废弃 daemon unit |

---

## 3. 分阶段长期开发路线图（M0 → M4）

### Phase 0（当前 · 1–2 周）：文档对齐 + 运维底座自动化（AI 自治闭环）

> **核心目标**：让 AI 彻底理解项目现状与双环境边界，跑通“云端备份 → 本地调试库 → 本地开发测试 → SSH 自动部署 → 线上体检”全自动流水线。

- [x] **M0.1 文档体系整理**：更新 `AGENTS.md`、`README.md`、`doc/README.md`、`doc/design/overview.md`、`doc/ENV.md`，标记废弃飞书支线，新增 `DevOps.md` 与 `ROADMAP.md`。
- [x] **M0.2 修复 P0 回归与清理基线**：恢复 `server.py` 中 `health_router` 挂载并补齐 `tests/server/test_router_mount.py` 回归拦截；补齐 `scripts/db_sync.py` 缺失的 `reminder`/`rhythm`/`tick` ORM 导入。
- [x] **M0.3 双环境基础设施脚本落地**：
  - 新增 `.env.ops.template`（凭据收敛，复用 `.env.prod`/`.env.dev`，不重复填密码）与 `.gitignore` 保护。
  - 落地 `scripts/ops/` 五件套：`doctor.py`、`backup_prod_db.py`、`restore_local_db.py`、`health_check.py`、`deploy_cloud.py`（自动探测 PostgreSQL 与 pgAdmin 4 客户端工具）。
  - 统一云端 `scripts/sailzen-server.service`，打通 `pnpm run build-site` → `SITE_DIST` 原子发布与自动回滚。
- [x] **M0.4 AI Ops Skill 落地**：编写完整版 `.agents/skills/sailzen-ops/SKILL.md`（含新开发机初始化、本地/远端校验、全链路演练与故障速查）及 `tests/unit/test_ops_scripts.py` 护栏单测。
- [x] **M0.5 本机实机联调验收（核心闭环已验证）**：已完成本机 `.env.ops` + SSH 免密 + 云端 PG 17.7 只读快照拉取（97.82 MB）→ 本机 PG 19 `main` 覆盖重构（9.6s / 55 表 / 78,629 行）→ 全模块 11/11 API 冒烟通过（后续可按需实跑一次 `deploy_cloud.py --dry-run` 与正式发布）。

**阶段验收标准**：从零开始做一个小改动，人类只下达需求并做最后验收，AI 在 10 分钟内独立完成“拉快照 → 建本地库 → 改代码跑测 → 上云部署 → 输出验收报告”。

---

### Phase 1（短期 · 2–4 周）：云端核心服务稳定性 + Android 随身闭环

> **核心目标**：打磨高频日常使用链路（财务、健康、节奏、提醒），让云端服务 + Android App 达到“每天无感稳定运行、零数据丢失”的生产级标准。

- [ ] **M1.1 生产数据安全网**：云端配置定时 `pg_dump`（cron/systemd timer）+ 定期同步备份到本地开发机，建立可验证的恢复演练机制。
- [ ] **M1.2 核心业务体验收敛**：
  - **健康模块**：巩固体重、饮食、运动、睡眠、用药在 Web 与 Android 端的双向一致，确保 `config/body_metrics.toml` 单一权威驱动三端。
  - **节奏模块（Rhythm）**：打磨日时间线、戒律打卡、周复盘与提醒规则联动，减少误打扰。
  - **财务模块**：固化账单导入（`sailzen-finance-bill-upload`）与自动打标（`sailzen-finance-auto-tags`）的半自动月度流水线。
- [ ] **M1.3 Android 发布效率提升**：脚本化 `assembleRelease` 签名构建与云端私有下载分发，缩短从修复 Bug 到装回真机的耗时。
- [ ] **M1.4 历史债务归档**：将 `sail_bot/`、`scripts/agent-daemon.service` 等停用支线正式归档至 `archive/`，保持主仓库清爽。

**阶段验收标准**：连续 30 天云端零意外宕机、每日备份可恢复；Android 提醒触达与离线队列同步稳定可用。

---

### Phase 2（中期 · 1–3 个月）：SailTick 实战稳定化 → 通用个人管家底座

> **核心目标**：先跑通“减肥监督教练”这一个真实闭环，再把验证成熟的 Tick 引擎泛化为覆盖健康/财务/节奏的通用 24/7 影子助手。

- [ ] **M2.1 SailTick 生产灰度跑通**：基于四层测试体系（[sailtick-testing.md](./design/agent-system/sailtick-testing.md)），在云端按 `shadow → canary → live` 完成 Day-1 到 Day-30 真实陪跑验收。
- [ ] **M2.2 反馈驱动的参数自调优**：依据票据响应率、安静时段与作息数据优化打扰度控制，沉淀稳定的人格 Prompt 与记忆压缩策略。
- [ ] **M2.3 领域泛化（从单一教练到个人管家）**：
  - 复用 `TickEngine` + `sail_tick_tickets` 票据协议 + 4 层记忆，逐步接入：
    - 财务异常扫描与月度预算预警（替代旧 `archive/autonomous_agent` 的单点 pipeline）。
    - Rhythm 晚间复盘、拖延干预与周报摘要。
    - 综合 Wellness 跨维度洞察（健康 + 财务 + 节奏联动）。

**阶段验收标准**：SailTick 持续 24/7 运行无静默崩溃、日均 Token 成本可控、票据响应率稳定、真正产生持续的行为改善价值。

---

### Phase 3（中长期 · 3–6 个月）：打通 VSCode 笔记生态与云端结构化数据（The Bridge）

> **核心目标**：在不破坏“Dendron 层级 Markdown + Git 同步”轻量纯粹性的前提下，用 Agent 与 `sailzen-cli` 搭起笔记与数据库之间的双向桥梁。

- [ ] **M3.1 稳定 VSCode 插件主干**：持续保持 Dendron 衍生插件的冷启动性能、树状层级体验与 Git 同步可靠性，不做侵入式改造（不把插件变成重型数据库客户端）。
- [ ] **M3.2 DB → Notes（自动沉淀）**：
  - SailTick / 周期任务通过 `sailzen-cli` 自动生成结构化日记切片、周复盘草稿、健康/财务月报 Markdown 写入个人 Vault（按 Git 分支或待审目录提交，人审后合并）。
- [ ] **M3.3 Notes → DB（语义抽取）**：
  - 从每日日记、读书/创作笔记中提取结构化事实（情绪/压力事件、灵感待办、人物/设定条目），以“待确认票据”形式呈报，经人确认后写入 PostgreSQL（Rhythm / Health / Text）。
- [ ] **M3.4 轻量双向引用**：完善 `NoteItem` / 双向链接规范，让 Web 端与 VSCode 笔记在语义上可互查，同时坚持**笔记归 Git、数据归 PG**的清晰存储解耦。

**阶段验收标准**：写日记后无需手工在多个界面重复录入；做周复盘时自动带出过去一周的体重、支出与事务完成事实。

---

### Phase 4（长期演进）：高自治个人影子助手

- **主动跨领域推理**：结合长期日记记忆、健康趋势、财务现金流与事业节奏，给出低频高质量的战略建议（而非碎片化提醒）。
- **受控自我演进**：结合 SailTick 的分支隔离自我开发机制（`agent/sailtick-dev`）与 Phase 0 建成的自动运维流水线，实现“AI 发现工具痛点 → 本地调试库验证 → 提 PR/Patch → 人类审阅验收 → 自动部署上线”的完整闭环。

---

## 4. 标准单轮迭代节奏（Iteration SOP）

后续每一轮功能版本迭代（无论大小），统一遵循以下 **5 步节奏**，避免文档再次漂移或上线踩坑：

1. **立项（人）**：一句话或简短清单明确本轮目标、涉及端（Backend / Site / Android / SailTick / Plugin）与“什么算完成”。
2. **数据对齐（AI）**：拉取云端最新快照重建本地调试库，确保在真实数据形态下开发。
3. **实现与自测（AI）**：
   - 修改代码 + 同步受影响文档/配置（如 `body_metrics.toml`、`ENV.md`、`API` 文档）。
   - 跑通对应端的单元测试、类型检查与本地冒烟。
4. **自动部署与自检（AI）**：云端库部署前备份 → 构建并发布 → 执行 `health_check.py` → 若失败则自动回滚并排查。
5. **验收与归档（人 + AI）**：人类按 AI 给出的验收清单在公网 Web / 手机端验证；确认通过后记录版本变更，进入下一轮。
