# Content 2.0（Phase 1）— 阅读库升级、多格式摄入与 Rhythm 专题联动

> **版本**: v2.0-phase1 | **日期**: 2026-11-26 | **状态**: ✅ Phase 1 已落地
> **关联文档**: [SailZen3.0.md](../../SailZen3.0.md) · [text.md](./text.md) · [rhythm.md](./rhythm.md) · [finance_sailtick.md](./finance_sailtick.md)

---

## 1. 定位与边界（Notes are notes. Databases are databases.）

- **本地 `D:\vault`（Git + Dendron Markdown）**：知识与长期创作权威源（日记 `journal.daily.*`、读书总览卡 `read.*`、划线托管文件 `read.*.clips`、专题笔记 `topic.*`、三大素养知识卡 `study.{tech|history|aesthetics}.*`、以及未来小说拆书/原创设定圣经 `read.*.bible.*`）。
- **云端 PostgreSQL（`sail_server`）**：结构化状态与跨端阅读库权威源（作品元数据 + 分卷树 + 云端阅读进度与会话 + 研究专题↔Rhythm 联动 + PDF/EPUB/参考图附件 + Vault 轻量元数据索引）。
- **SailTick**：通过 `DataScanner` 只读感知 `/api/v1/text/progress/overview`（主线在读、三大素养近 7 天阅读时长、停滞主线书目）。

---

## 2. 数据模型演进（Expand-Only 幂等迁移）

ORM 定义于 `packages/py/sailzen-orm/sailzen_orm/text.py`，PostgreSQL 迁移动作位于 `sail_server/migration/20261126_content_v2_reading_library.sql`：

1. **`works` 增量字段**：`pillar`（`tech|history|aesthetics|fiction|general`）、`reading_status`（`inbox|queued|reading|paused|finished|dropped`）、`reading_track`（`mainline|project|leisure`）、`priority`、`source_url`、`vault_slug`、`is_original`。
2. **`document_nodes` 分卷树形结构**：`node_type='volume'` 作为卷父节点（`depth=0, path='V0001'`），章节挂 `parent_id` 且保持全本 `sort_index` 线性递增以 100% 兼容旧翻页接口；补齐 `(edition_id, node_type, sort_index)` 与 `(edition_id, parent_id, sort_index)` 索引。
3. **`reading_progress`**：云端权威阅读进度（按 `last_read_at` LWW 合并多端冲突，自动重算全本 `progress_pct` 并推进 `queued → reading`）。
4. **`reading_sessions`**：轻量阅读会话记录，按 `pillar` 聚合 7d/30d 投入时长。
5. **`content_topics` & `content_topic_works`**：研究专题与多对多作品关联，通过 `rhythm_venture_id` 绑定 `RhythmAffair(kind='venture')`，并支持一键向 Rhythm 推送带反向引用的里程碑子任务。
6. **`content_assets`**：论文原 PDF、EPUB 源文件与审美参考图存储（上限 100MB，存储于 `SERVER_DATA_DIR/content_assets`）。
7. **`vault_note_index`**：`D:\vault` 中 `read.*` / `topic.*` / `study.*` 的轻量只读索引（按 `content_hash` 幂等同步）。

---

## 3. 核心 API 契约（`/api/v1/text/...`）

| 领域 | 端点 | 说明 |
|---|---|---|
| **作品与筛选** | `GET /text/work?pillar=&reading_status=&work_type=&topic_id=` | 列表自动内联云端进度、关联专题 ID 与附件数 |
| **分卷目录** | `GET /text/edition/{id}/toc` · `POST /volumes` · `POST /auto-volume` | 分卷树形目录、手动建卷归组、扁平小说自动识别/预览分卷 |
| **多格式导入** | `POST /text/import/create` · `/epub` · `/pdf` · `/arxiv` | 补齐 TXT 分批建壳；EPUB 自动还原卷树；PDF/arXiv 双轨保留（分节正文 + 原 PDF 附件） |
| **云端进度** | `GET/PUT /text/progress/{work_id}` · `POST /progress/sync` · `POST /progress/session` · `GET /progress/overview` | Web/Android 双向进度同步、会话上报与素养概览 |
| **专题联动** | `GET/POST/PUT/DELETE /text/topic` · `GET /topic/{id}/detail` · `POST /topic/{id}/works` · `POST /topic/{id}/push-rhythm-task` | 专题书单管理、实时聚合 Rhythm Venture 与子任务、一键推任务进 Rhythm |
| **附件与 Vault** | `GET/POST/DELETE /text/asset` · `GET /work/{id}/export-clips` · `POST/GET /text/vault/index` | PDF/参考图在线预览、导出带受控围栏的 Dendron 读书卡与划线文件、同步 Vault 索引 |

---

## 4. CLI 与多端协同

- **Vault 双向同步 CLI**：
  ```powershell
  uv run --package sailzen-cli sailzen vault sync-content --vault-dir D:\vault --dry-run
  uv run --package sailzen-cli sailzen vault sync-content --vault-dir D:\vault
  ```
  - 上行：扫描 `read.*` / `topic.*` / `study.*` 元数据至 `vault_note_index`。
  - 下行：导出活跃作品的 `read.<slug>.clips.md` 与 `read.<slug>.md`，后者仅更新 `<!-- sailzen:managed:meta:start --> ... <!-- sailzen:managed:meta:end -->` 围栏区块，绝不覆盖手写笔记。
- **Web 管理台**：`/text`（阅读库 + 分卷目录 + PDF 侧栏对照 + 多格式导入）、`/topics`（专题研究工作台 + Rhythm 联动）；原测试性质的 `/info` 旧历史事件表已从主导航归档下线（`history_events` 表保留不删）。
- **Android 端**：Room 升级至 v8，书架支持素养/主线筛选与进度条，目录抽屉支持分卷折叠，阅读进度本地秒写并后台双向同步云端。
