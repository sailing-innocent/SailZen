# Helpful Scripts

## 1. `scripts/ops/` — 双环境自动化运维套件（Phase 0）

所有脚本均收敛凭据：**生产/本地 DB 密码与 Token 直接读取 `.env.prod` / `.env.dev`**，SSH 与云端部署参数配置在 `.env.ops`（模板见 [`.env.ops.template`](../.env.ops.template)）。支持自动探测本机 PostgreSQL 与 pgAdmin 4 runtime 中的 `pg_dump` / `pg_restore` / `psql`。

```powershell
# 1. 双环境诊断（加 --check-remote 实测生产 PG 只读连通与 SSH 登录）
uv run python scripts/ops/doctor.py
uv run python scripts/ops/doctor.py --check-remote

# 2. 云端生产库只读备份（默认 direct 模式，也支持 --mode ssh）
uv run python scripts/ops/backup_prod_db.py
uv run python scripts/ops/backup_prod_db.py --dry-run

# 3. 从最新快照覆盖更新本地调试 PG（硬护栏：仅允许 localhost/127.0.0.1；含序列修复、迁移自检与行数核验）
uv run python scripts/ops/restore_local_db.py
uv run python scripts/ops/restore_local_db.py --pull          # 一键：云端拉新快照 + 覆盖本机调试库
uv run python scripts/ops/restore_local_db.py --dry-run

# 4. 本地 / 云端只读健康体检（含全部核心业务 GET 路由 + 可选 SailTick :9070）
uv run python scripts/ops/health_check.py --env dev
uv run python scripts/ops/health_check.py --env prod --with-sailtick

# 5. 云端自动化部署（本地门禁 → 生产库备份 → 构建并原子替换 site_dist → 同步代码 → 重启 → 体检；失败自动回滚）
uv run python scripts/ops/deploy_cloud.py --dry-run
uv run python scripts/ops/deploy_cloud.py
uv run python scripts/ops/deploy_cloud.py --rollback <PREV_COMMIT>
```

配套 systemd unit 模板：
- `scripts/sailzen-server.service`（云端 `sail_server`）
- `scripts/sailtick.service`（云端 `sailtick` daemon）

详见 [doc/maintain/DevOps.md](../doc/maintain/DevOps.md) 与 `.agents/skills/sailzen-ops/SKILL.md`。

---

## 2. `generate_body_metrics.py` — 内置身体指标注册表代码生成

`config/body_metrics.toml` 是内置身体指标（BUILTIN_METRICS）的**单一权威**。
三端 + mock 的注册表镜像均由该文件代码生成，不要手工同步多份清单：

- `sail_server/application/dto/body_data.py`（后端）
- `site/src/lib/data/body_data.ts`（site 前端）
- `android/app/src/main/java/com/sailzen/app/core/network/dto/BodyDataDtos.kt`（Android）
- `site/mock/server.js`（mock，仅开发用）

```powershell
# 修改 config/body_metrics.toml 后重新生成四处镜像
uv run python scripts/generate_body_metrics.py

# 校验生成物是否最新（tests/unit/test_body_metrics_codegen.py 也会强制执行）
uv run python scripts/generate_body_metrics.py --check
```

生成块位于各文件的 `BEGIN/END GENERATED BODY METRICS` 标记之间，请勿手改；
`tests/unit/test_body_metrics_codegen.py` 保证生成物与配置永远同步。
