# SailZen 健康管理升级（SailTick AI 教练 + 动态计划 + 睡前日报）接续部署与验收手册

> **版本**: v1.0 | **日期**: 2026-11-22 | **适用范围**: 首次「本地 AI 迭代 → 人工接续推送/上云/装机」闭环演练
> **前置状态**: 本地代码实现、PostgreSQL 生产快照迁移验证、后端/SailTick 四层测试（Layer 1/2 + E2E Smoke）、Web 生产构建、Android Debug 编译与 Kotlin 单测已全部在本地验证通过。

---

## 0. 本次升级内容与运维基建优化速览

### 0.1 健康管理核心升级（4 端联动）
1. **后端 & ORM（`packages/py/sailzen-orm/` + `sail_server/`）**
   - **AI 动态体重计划**：扩展 `weight_plans`（`managed_by`, `plan_version`, `phase_name`, `phase_rationale`, `focus_notes`, `daily_targets`, `tolerance_kg`, `ai_summary`），新增 `POST /api/v1/health/weight/plan/ai-sync`；现有 `/weight/target`、`/weight/plan/progress`、`/weight/plan/expected`、`/weight/plan/weights-with-status`、`/dashboard` 全部升级为优先按 AI 动态分段节点插值与弹性容忍带宽评估，替代死板机械线性计划。
   - **静默餐饮/状态主动上报**：新增 `sail_tick_messages` 表与 `POST/GET /api/v1/tick/messages`、`POST /api/v1/tick/messages/ingest`。用户在 App/Web 主动发送饮食文字时，无需等待 AI 立即回复，系统同步落一条轻量 `DietLog` 供健康页立即可见，SailTick 在后续 Tick / 睡前日报自动吸收并标记 `ingested`。
   - **每日睡前体重与健康日报**：新增 `sail_tick_daily_reports` 表与 `POST/GET /api/v1/tick/reports`、`GET /reports/latest`、`GET /health-summary`。
   - **Android 推送可靠性修复**：SailTick 提问票据与睡前日报推送时持久化真实 `Reminder(source="agent")` 记录再经 WS 广播，离线时 WorkManager `/reminder/pending` 可靠补齐、零 ID 冲突；用户回复票据后自动关闭关联提醒。
   - **Expand-and-Contract 迁移**：新增幂等 PostgreSQL 迁移 `sail_server/migration/20261122_health_sailtick_upgrade.sql`（仅增列/增表/增索引，支持安全回滚）。
2. **SailTick 守护进程（`sailtick/`）**
   - **修复生产环境致命问题**：自动加载 `.env.prod`（不覆盖已有环境变量）、修复 `--config` 参数位置崩溃、修复 `daemon.py` 调度器启动顺序、修复 `_inbox_loop` 重复刷库游标、全面修复 `datascan.py` 多个 404/422 路由与字段漂移。
   - **体重更新监控 + 渐进提问防轰炸**：计算体重最新变化/距上次称重时长/7日均值/异常波动，接入 `question_bank.yaml` 与 `slot_*.md`，生产配置硬限流（每 Tick 最多 1 题、未回复达到 2 题暂停新提问、同话题 24h 冷却）。
   - **每日 21:45 睡前日报 (`pre_sleep_report`) + AI 计划闭环写回**：整合当日体重、饮食、用户主动消息与票据回复，执行 `profile_update` / `plan_update` / `daily_report` / `resolve_ticket` / `ingest_messages`；LLM 不可用时仍能产出数据驱动的兜底日报。
3. **Web 管理台（`site/`）**
   - `/health` 新增 `SailTickCoachPanel`（待回提问快捷回复、随手静默记餐饮、近 7 天睡前日报查阅），`Current Weight Plan` 卡片升级展示 `SailTick AI 动态计划`（阶段、版本、评语、节奏依据、关注点、弹性带宽）。
   - `/tick` 同步补齐静默餐饮发送与最新睡前日报卡片。
4. **Android App（`android/`）**
   - 新增 `TickApi` / `TickDtos` / `TickRepository` 及全新 **`HealthCoachScreen`**（提问卡片 + 快捷回复芯片 + 静默餐饮上报 + 睡前日报历史）。
   - `HealthHomeScreen` 顶部新增 **SailTick AI 教练动态卡片**（待回复计数、最新日报摘要、一键记体重/随手记一餐）。
   - `WeightPlanScreen` 升级展示 AI 动态计划并修复控制率百分比显示。
   - `InboxScreen` 支持对 `tick.ticket.*` 提醒**收件箱内直接回复教练**，对 `tick.daily_report` 支持**一键跳转完整日报**；修复 `CachedReminder.payloadJson` 为合法 JSON（Room DB v5 → v6 自动重建本地缓存，云端主库无影响）。

### 0.2 本次顺手修复的 DevOps 基建缺陷
- `scripts/sailtick.service`：修复 `%I` 非模板 unit 占位符 bug、修复 `--config` CLI 参数顺序、对齐 `/home/ubuntu/repos/SailZen` 与 `/home/ubuntu/.local/bin/uv`、补充 `EnvironmentFile=-/home/ubuntu/repos/SailZen/.env.prod`。
- `scripts/ops/deploy_cloud.py`：修复回滚导致远端仓库进入 detached HEAD 的问题；远端前端构建前补齐 `pnpm install`；本地门禁纳管 Health/Tick/SailTick 测试；失败时同时拉取 `sailtick.service` 日志。
- `scripts/ops/health_check.py`：探针扩展至 17 个核心只读路由（覆盖 `/health/dashboard`、`/health/diet`、`/health/weight/plan`、`/tick/health-summary`、`/tick/reports`、`/tick/messages`），`--with-sailtick` 深度校验 `/monitor` 与熔断状态。
- `scripts/ops/backup_prod_db.py`：`--mode ssh` 改为流式输出直写本地，彻底消除远端 `/tmp` 权限与残留问题。
- `scripts/ops/build_android_release.py`（新增）：Android Release 打包护栏脚本，拒绝空公网地址或意外回退 debug 签名，自动输出 APK 体积与 SHA256。
- `doc/maintain/DevOps.md`：脱敏清理此前误留的公网 IP 与本机用户名路径。

---

## 1. 步骤一：本地提交与合入云端目标分支

> 预演探测显示：当前云端仓库位于 **`master`** 分支，而本地开发分支为 **`ai`**。

1. **在本地检查变更并提交**（遵循 `commit-current-change` 规范）：
   ```powershell
   git status -sb
   # 确认无敏感文件（.env.* / data/backups / keystore）且无 Windows `nul` 文件
   git add -A
   git commit -m "feat(health,sailtick,android,ops): upgrade health management with SailTick AI coach, dynamic plan & daily reports"
   ```
2. **推送或生成 Patch 合入 `master`**：
   - 若你在允许推送的环境（`$env:ALLOW_PUSH=1`）：将 `ai` 合并或变基到 `master` 后执行 `git push origin master`。
   - 若暂不推送 `origin`，也可直接用 `deploy_cloud.py --sync-mode patch` 上传增量补丁到云端应用（请先确保云端 `master` 与本地共同祖先一致）。

---

## 2. 步骤二：云端服务器部署（`sail_server` + `site_dist` + `sailtick`）

### 2.1 核对云端 `.env.prod` 环境变量（只需做一次）

SSH 登录云端服务器，检查 `/home/ubuntu/repos/SailZen/.env.prod` 是否已配置以下键（不要泄露到 Git）：

```bash
ssh sailzen-prod
nano ~/repos/SailZen/.env.prod
```

确认或补充：
```dotenv
# SailTick 使用的 LLM Key（二选一或同时配置，优先使用 SAILTICK_LLM_DEFAULT 指定的 provider）
DEEPSEEK_API_KEY=<你的 DeepSeek Key>
# 或使用 Moonshot / Kimi：
# MOONSHOT_API_KEY=<你的 Moonshot Key>
# SAILTICK_LLM_DEFAULT=kimi

# 与 sail_server 共用的鉴权 Token（若已启用鉴权务必保持一致）
SAILZEN_API_TOKEN=<你的 Token>

# 首次上线强烈建议先走 shadow 或 canary 灰度观察 1-2 个 Tick，确认无误后再切 live
SAILTICK_MODE=shadow
```

> **提示**：不要直接修改云端仓库里的 `sailtick.yaml`（已被 Git 追踪），所有环境差异均通过 `.env.prod` 中的 `SAILTICK_*` 覆盖，保证后续 `git pull --ff-only` 永远干净无冲突！

### 2.2 发布后端与 Web 前端（先不含 SailTick）

回到本地 Windows PowerShell：

```powershell
# 1. 先预演一遍（零副作用）
uv run python scripts/ops/deploy_cloud.py --dry-run

# 2. 正式发布 sail_server + site_dist（自动完成：本地门禁 → 生产库热备 → 同步代码 → 构建前端 → 重启服务 → 17 项线上健康体检）
uv run python scripts/ops/deploy_cloud.py
```

验证看到 `Result: 18/18 passed.`（含 Web Root + 17 个只读 API 探针）后再继续下一步。

### 2.3 首次安装并初始化云端 `sailtick.service`

SSH 登录云端服务器执行一次安装：

```bash
ssh sailzen-prod
cd ~/repos/SailZen

# 1. 复制 systemd unit（注意：若当前后端服务名仍为 my-server.service，将 After/Wants 中的 sailzen-server.service 替换为 my-server.service）
sudo cp scripts/sailtick.service /etc/systemd/system/sailtick.service
sudo sed -i 's/sailzen-server.service/my-server.service/g' /etc/systemd/system/sailtick.service

# 2. 确认 /etc/sudoers.d/sailzen-ops 已放行 ubuntu 免密控制 sailtick.service（见 .agents/skills/sailzen-ops/SKILL.md §1.4）
sudo systemctl daemon-reload

# 3. 依赖体检（校验 SQLite、sail_server 连通性、LLM Key、目录可写）
SAILTICK_ENV=prod uv run python -m sailtick doctor

# 4. 首次初始化基线（若之前未跑过 bootstrap：写入目标 70kg、初始计划 v0.1）
SAILTICK_ENV=prod uv run python -m sailtick bootstrap

# 5. 设置首次启动模式为 shadow（影子运行，零推送副作用）并启动常驻服务
SAILTICK_ENV=prod uv run python -m sailtick canary set shadow --reason "initial cloud rollout"
sudo systemctl enable --now sailtick.service
sudo systemctl status sailtick.service --no-pager
```

### 2.4 SailTick 三步安全灰度放量（`shadow` → `canary` → `live`）

1. **阶段 A：Shadow 影子演练（建议跑 1 次手动触发 + 观察日志）**
   ```bash
   # 在云端查看监控快照
   SAILTICK_ENV=prod uv run python -m sailtick monitor
   # 实时看日志
   sudo journalctl -u sailtick.service -n 50 --no-pager
   ```
   回到本地验证联合体检（含 SailTick `:9070/health` + `:9070/monitor`）：
   ```powershell
   uv run python scripts/ops/health_check.py --env prod --with-sailtick
   ```
2. **阶段 B：Canary 灰度模式（真实建票据但限流 1 张/Tick、暂不打扰推送）**
   ```bash
   ssh sailzen-prod "cd ~/repos/SailZen && SAILTICK_ENV=prod uv run python -m sailtick canary set canary --prefix '[Coach] ' --reason 'verify ticket & report quality'"
   ```
   打开公网 Web `/health` 或 `/tick` 查看 AI 产出的提问与动态计划质量。
3. **阶段 C：Live 正式运行（开启 Android 推送 + 每日 21:45 睡前日报 + AI 动态计划维护）**
   - 记得将云端 `.env.prod` 中的 `SAILTICK_MODE=shadow` 改为 `SAILTICK_MODE=live`（或删去该行），然后热切：
   ```bash
   ssh sailzen-prod "cd ~/repos/SailZen && SAILTICK_ENV=prod uv run python -m sailtick canary set live --reason 'promote to live'"
   ```
   此后日常升级可直接使用一条命令同时发版两端：
   ```powershell
   uv run python scripts/ops/deploy_cloud.py --with-sailtick
   ```

---

## 3. 步骤三：构建并安装新版 Android App

### 3.1 检查本机 Gradle Release 凭据

确认 `C:\Users\<你的用户名>\.gradle\gradle.properties` 中已配置公网地址与正式签名信息（严禁提交到仓库）：

```properties
SAILZEN_RELEASE_SERVER_URL=http://<你的云端域名或IP>:1974
SAILZEN_STORE_FILE=F:/path/to/your/release.keystore
SAILZEN_STORE_PASSWORD=<keystore密码>
SAILZEN_KEY_ALIAS=<key别名>
SAILZEN_KEY_PASSWORD=<key密码>
```

### 3.2 使用新运维脚本构建 Release APK

```powershell
# 1. 前置护栏校验（不执行构建）
uv run python scripts/ops/build_android_release.py --dry-run

# 2. 运行 Kotlin 单测 + 构建正式签名 APK 并输出 SHA256
uv run python scripts/ops/build_android_release.py --with-tests
```

> 若仅想先装 Debug 包到测试机：运行 `uv run python scripts/ops/build_android_release.py --debug --with-tests`。

### 3.3 安装到手机

- **USB / 无线 ADB 直装**：
  ```powershell
  adb devices
  adb install -r android\app\build\outputs\apk\release\app-release.apk
  ```
- **或手工传输 APK**：将上述路径的 `.apk` 发送到手机点击覆盖安装。
- *升级说明*：本次 Room 本地缓存数据库从 v5 升至 v6，App 首次启动会自动重建本地提醒缓存并从云端重新同步，**云端数据与用户配置（`SettingsManager`）均不受影响**。

---

## 4. 步骤四：上线后体验验收清单

- [ ] **Web `/health`**：顶部可见「随手记餐饮/发给教练」「每日睡前体重与健康日报」，体重计划卡片在 SailTick 首次 `plan_update` 后显示 `AI 动态体重计划`、`SailTick 托管`、当前阶段名与 AI 评语。
- [ ] **Android 健康首页**：顶部显示「SailTick AI 健康教练」卡片，点击可进入全新 `HealthCoachScreen`。
- [ ] **主动静默记饮食**：在 Android `HealthCoachScreen` 选「午餐」输入一条描述点「静默记录」→ 立即提示「已静默记录，SailTick 将在今晚睡前日报中整合分析」，健康→饮食页立即可见该条目，且不阻塞等待 AI 回复。
- [ ] **渐进式提问 & 收件箱直回**：当 SailTick 发出 1 条提问票据时，手机收到通知并在收件箱显示；可直接在收件箱卡片输入框点击「回复」，回复后该收件箱卡片自动关闭。
- [ ] **每日睡前日报**：21:45（或手动 `sailtick trigger pre_sleep_report` 触发）手机收到睡前日报推送，点击「查看完整日报」进入 `HealthCoachScreen` 可见完整体重趋势、餐饮整合与明日建议。

---

## 5. 应急止血与回滚命令

- **仅紧急暂停 SailTick（一键总闸，不影响后端与 App 其他功能）**：
  ```bash
  ssh sailzen-prod "cd ~/repos/SailZen && SAILTICK_ENV=prod uv run python -m sailtick canary kill --reason 'manual stop'"
  # 或直接停服务：
  ssh sailzen-prod "sudo systemctl stop sailtick.service"
  ```
- **完整回滚后端与前端到上一个 commit**：
  ```powershell
  uv run python scripts/ops/deploy_cloud.py --rollback <PREV_COMMIT>
  ```
  > 本次数据库迁移严格遵循 Expand-and-Contract（只增不删），代码回滚无需回滚数据库即可无缝兼容。
