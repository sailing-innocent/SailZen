---
name: sailzen-ops
description: |
  SailZen 双环境完整自动化运维技能（Windows 本地开发调试机 vs 公网 Linux 云服务器）。
  覆盖：全新开发机从零初始化（工具链/三套.env凭据收敛/SSH免密密钥与sudoers）、
  本机开发环境校验、远端生产环境校验、以及“拉取快照 → 覆盖本地调试库 → 本地开发与门禁 → 自动发布上云 → 线上回归与自动回滚”
  完整闭环的标准执行与零副作用演练。
---

# SailZen 全流程自动化运维指南（DevOps Skill）

本技能沉淀 SailZen **「人做规划与验收，AI 做本地迭代与自动运维」** 的全套标准作业程序（SOP），适用于：
- 初始化一台全新 Windows 开发机并打通云端生产环境
- 校验本机调试环境与远端部署环境健康度
- 演练或正式执行 **拉取（Pull）→ 覆盖（Overwrite）→ 本地开发（Dev）→ 发布（Release）→ 回归（Regression）** 完整迭代循环

关联文件：
- 运维脚本：`scripts/ops/`（`common.py` / `doctor.py` / `backup_prod_db.py` / `restore_local_db.py` / `health_check.py` / `deploy_cloud.py`）
- 配置模板：`.env.template`、`.env.ops.template`、`scripts/sailzen-server.service`、`scripts/sailtick.service`
- 架构与手册：`doc/maintain/DevOps.md`、`doc/ROADMAP.md`、`AGENTS.md`

---

## 0. 核心原则与不可逾越的红线

1. **凭据收敛，不重复填密码**：
   - `.env.prod`：生产库 `POSTGRE_URI`、`SAILZEN_API_TOKEN`、`SERVER_PORT`、LLM Key 的唯一权威源。
   - `.env.dev`：本机调试库 `POSTGRE_URI`（默认指向 `localhost:5432/main`）与本地调试端口。
   - `.env.ops`：仅存 SSH 别名、云端仓库路径、systemd 服务名、备份与前端构建策略（若把 `OPS_*` 写在 `.env.prod`，脚本也会自动兜底读取）。
   - **严禁读取并打印真实密码/Token/私钥内容，严禁提交 `.env.*`、`data/backups/`、`*.dump`、`android/keystore/`**。
2. **只读拉生产，本地随便改**：绝不用开发代码直连/修改生产 PostgreSQL；所有调试在本地 `main` 调试库完成，`restore_local_db.py` 内置硬护栏（目标 Host 必须为 `localhost` / `127.0.0.1` / `::1`）。
3. **先备份、先预演、再上线**：发布前先跑 `--dry-run`；正式 `deploy_cloud.py` 强制先执行生产库备份再变更代码与前端，**禁止随意使用 `--skip-backup`**。
4. **遵循 Git 推送约束**：未设置 `$ALLOW_PUSH=1` 时禁止 `git push origin`（见 `git-push` / `finalize-today-work` skill）；本地未推 `origin` 时，发布可使用 `deploy_cloud.py --sync-mode patch`。
5. **Windows PowerShell (`pwsh`) 规范**：用 `;` 分隔命令，不用 `&&`；Python 命令统一用 `uv run`。

---

## 1. 阶段一：初始化一台新开发机（New Dev Machine Bootstrap）

### 1.1 安装基础工具链

在新 Windows 开发机上安装以下组件：
- **Python 包管理**：`uv`（Python >= 3.13）
- **前端与插件**：Node.js + `pnpm`
- **版本控制与远程**：`git`、Windows 内置 OpenSSH（`ssh` / `scp`）
- **本地 PostgreSQL 调试库**：安装 PostgreSQL（推荐 ≥ 云端版本，如 PG 17–19）或 pgAdmin 4。
  > 无需手工把 PG 加入系统 PATH：`scripts/ops/common.py` 会按 `OPS_PG_BIN_DIR` → `PATH` → `C:\Program Files\PostgreSQL\<最高版本>\bin` → `pgAdmin 4\runtime` 自动探测 `pg_dump` / `pg_restore` / `psql`。
- **Android 开发（按需）**：Android Studio + JDK 17 + `adb`（签名凭据放 `~/.gradle/gradle.properties`，严禁入库）。

### 1.2 拉取仓库与安装依赖

```powershell
git clone <repo-url> SailZen
cd SailZen
uv sync
pnpm install
```

### 1.3 准备三份本地环境配置文件（全部已被 `.gitignore` 排除）

```powershell
Copy-Item .env.template .env.dev
Copy-Item .env.template .env.prod
Copy-Item .env.ops.template .env.ops
```

按以下分工填写：

1. **`.env.dev`（本机默认调试库，可随时被生产快照覆盖）**：
   ```dotenv
   DB_BACKEND=postgres
   POSTGRE_URI=postgresql://postgres:<本机PG密码>@localhost:5432/main
   SERVER_PORT=4399
   LOG_LEVEL=DEBUG
   DB_DEBUG=true
   REMINDER_ENABLED=false   # 防止本地调试误推真机通知
   ```
2. **`.env.prod`（只读备份与线上体检的凭据源）**：
   ```dotenv
   DB_BACKEND=postgres
   POSTGRE_URI=postgresql://postgres:<云端PG密码>@<云端IP>:5432/main
   SERVER_PORT=1974
   SAILZEN_API_TOKEN=<云端鉴权Token，未启用可留空>
   ```
3. **`.env.ops`（SSH 与云端部署元数据，不含数据库密码）**：
   ```dotenv
   OPS_BACKUP_MODE=direct
   OPS_BACKUP_DIR=data/backups
   OPS_BACKUP_KEEP_DAYS=14
   OPS_SSH_HOST=sailzen-prod
   OPS_SSH_USER=ubuntu
   OPS_REMOTE_REPO=/home/ubuntu/repos/SailZen
   OPS_REMOTE_SITE_DIST=/home/ubuntu/repos/SailZen/site_dist
   OPS_REMOTE_SERVER_SERVICE=my-server.service   # 或迁移统一后的 sailzen-server.service
   OPS_REMOTE_SAILTICK_SERVICE=sailtick.service
   OPS_REMOTE_UV_BIN=uv
   OPS_REMOTE_PNPM_BIN=pnpm
   OPS_SITE_BUILD_MODE=remote                    # 云端执行 pnpm build-site；也可选 local
   OPS_REMOTE_USE_SUDO=true
   ```

### 1.4 配置 SSH 免密专用密钥与云端最小权限 `sudo`

> **⚠️ 避坑提示**：在 Windows PowerShell 中直接执行 `ssh-keygen -N '""'` 会把两个字面引号 `""` 设为私钥口令！请务必使用下面 Python 调用方式生成真正空口令的专用部署密钥。

```powershell
# 1. 生成真正空口令的专用部署密钥（若已存在请先确认不要覆盖）
uv run python -c 'import subprocess, os; p = os.path.expanduser("~/.ssh/id_ed25519_sailzen"); subprocess.run(["ssh-keygen", "-t", "ed25519", "-f", p, "-N", "", "-C", "sailzen-ops"], check=True)'

# 2. 将公钥写入云端（最后一次输入云端登录密码）
$pubKey = Get-Content "$env:USERPROFILE\.ssh\id_ed25519_sailzen.pub" -Raw
$pubKey | ssh <云端用户>@<云端IP> "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

在 `C:\Users\<用户名>\.ssh\config` 中新增别名（与 `.env.ops` 中 `OPS_SSH_HOST=sailzen-prod` 对应）：

```sshconfig
Host sailzen-prod
    HostName <云端IP>
    User ubuntu
    Port 22
    IdentityFile ~/.ssh/id_ed25519_sailzen
    IdentitiesOnly yes
    ServerAliveInterval 60
```

在云端为非 `root` 用户配置最小权限 `sudo` 免密（只需做一次，在云端执行 `sudo visudo -f /etc/sudoers.d/sailzen-ops`，将服务名替换为实际值）：

```sudoers
ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart my-server.service, /bin/systemctl status my-server.service, /bin/systemctl is-active my-server.service, /bin/systemctl restart sailzen-server.service, /bin/systemctl status sailzen-server.service, /bin/systemctl is-active sailzen-server.service, /bin/systemctl restart sailtick.service, /bin/systemctl status sailtick.service, /bin/systemctl is-active sailtick.service, /bin/systemctl stop sailtick.service, /bin/journalctl
```

（若未来希望用 `--mode ssh` 在云端本地压缩备份以提速，可在同一文件中追加 `, /usr/bin/pg_dump` 供 `sudo -u postgres pg_dump` 免密执行。）

---

## 2. 阶段二：校验本机开发环境（Local Dev Check）

按顺序执行，全部通过即说明本机调试环境就绪：

```powershell
# 1. 确认本机 PostgreSQL 服务正在运行
Get-Service *postgres* | Select-Object Name, Status, StartType

# 2. 运行本机环境诊断（自动检测 .env 三件套、CLI、PG/pgAdmin4 工具、本机 PG 连通性）
uv run python scripts/ops/doctor.py

# 3. 运行运维护栏、路由挂载与代码生成回归测试
uv run pytest tests/unit/test_ops_scripts.py tests/server/test_router_mount.py tests/unit/test_body_metrics_codegen.py -v
```

期望验收标准：
- `doctor.py` 输出 `0 failure(s)`，且 `本地调试库 (.env.dev)` 明确标记 `[安全: 本机地址]`、`连通性: 本地 PG` 显示本机 PostgreSQL 版本。
- `pytest` 全部 `PASSED`。

---

## 3. 阶段三：校验远端部署环境（Remote Prod Check）

所有检查均为**只读**，不会修改生产状态：

```powershell
# 1. 验证 SSH 非交互免密登录
ssh -o BatchMode=yes sailzen-prod "echo ok && hostname"

# 2. 双环境联合体检（含生产 PG 只读 SELECT version() 与 SSH 探测）
uv run python scripts/ops/doctor.py --check-remote

# 3. 核对云端仓库、分支、前端构建工具、uv 与 sudo 免密重启权限（按实际路径与服务名）
ssh -o BatchMode=yes sailzen-prod "cd ~/repos/SailZen && git status -sb && git log -1 --oneline && which uv pnpm && sudo -n systemctl is-active my-server.service"

# 4. 线上 HTTP 只读健康体检（校验首页 + 11 个核心业务只读 API 路由）
uv run python scripts/ops/health_check.py --env prod
# 如已部署 SailTick，可追加 --with-sailtick
```

期望验收标准：
- `doctor.py --check-remote` 全部 `[OK]`（`0 failure(s)`）。
- 云端 `git status -sb` 干净、`sudo -n systemctl is-active` 返回 `active` 且不提示输密码。
- `health_check.py --env prod` 全部核心接口返回 `200`。

---

## 4. 阶段四：完整迭代循环与演练（Pull → Overwrite → Dev → Release → Regression）

### 4.1 零副作用全链路演练（新开发机 / 首次联调推荐先跑一遍）

以下命令不会改动云端代码或生产数据，用于一次性演练整条流水线：

```powershell
# Step A: 校验双环境连通性
uv run python scripts/ops/doctor.py --check-remote

# Step B: 演练拉取云端备份（--dry-run 不落盘；去掉 --dry-run 可真实只读拉取一份快照）
uv run python scripts/ops/backup_prod_db.py --dry-run

# Step C: 演练覆盖本地 main 调试库（--dry-run 不修改本地库）
uv run python scripts/ops/restore_local_db.py --dry-run

# Step D: 运行本地发布门禁（代码生成校验 + 核心测试 + 前端构建检查）
uv run python scripts/generate_body_metrics.py --check
uv run pytest tests/server/test_router_mount.py tests/unit/test_ops_scripts.py tests/unit/test_body_metrics_codegen.py -q
pnpm run build-site

# Step E: 演练云端发布（探测云端 HEAD、打印将要执行的同步/构建/重启/体检步骤，不改生产）
uv run python scripts/ops/deploy_cloud.py --dry-run

# Step F: 线上当前状态只读回归体检
uv run python scripts/ops/health_check.py --env prod
```

### 4.2 标准日常迭代闭环（正式执行 SOP）

每一轮新功能或 Bug 修复，严格按以下 **5 步** 推进：

#### ① 拉取 & 覆盖本地调试库（Pull + Overwrite）

```powershell
# 场景 1：已有近期快照，仅需快速回血/重置本机 main 调试库（~10s，含全表序列修复+迁移自检+行数核验）
uv run python scripts/ops/restore_local_db.py

# 场景 2：需要云端最新生产数据，一条命令“只读备份云端 + 立即覆盖本机 main”
uv run python scripts/ops/restore_local_db.py --pull

# 场景 3：仅做只读归档备份（不覆盖本地库）
uv run python scripts/ops/backup_prod_db.py
# 若云端 5432 未对外开放或想在云端本地压缩提速，使用 --mode ssh
```

#### ② 本地开发与本地回归（Local Dev）

```powershell
# 终端 1：启动本地调试后端（加载 .env.dev，直连刚覆盖好的本机 PG main）
uv run server.py --dev

# 终端 2（如改 Web 前端）：启动 Vite 热重载
pnpm run dev:site

# 终端 3：本地只读健康体检 + 自动化测试
uv run python scripts/ops/health_check.py --env dev
uv run python scripts/generate_body_metrics.py --check
uv run pytest tests/unit tests/server tests/sailtick -m "not current and not live_llm"
```

#### ③ 代码提交 / Patch 交付

- 按 `commit-current-change` skill 清理 `nul` 并提交本地 commit。
- 若本机受 `$ALLOW_PUSH` 约束不能直接 `git push origin`：
  - 方案 1：按 `finalize-today-work` 产出 patch 并在允许 push 的环境合入 `origin` 后，用默认的 `--sync-mode git` 部署；
  - 方案 2：直接用 `deploy_cloud.py --sync-mode patch` 将本地相对云端 `HEAD` 的增量 patch 上传并 `git am` 到云端。

#### ④ 自动发布上线（Release）

```powershell
# 1. 必做：先 dry-run 核对远端当前 commit 与发布动作
uv run python scripts/ops/deploy_cloud.py --dry-run

# 2. 正式发布（自动：本地门禁 → 生产库热备 → 记录 PREV_COMMIT → 同步代码与 uv sync
#            → 构建/更新前端 site_dist → 重启 systemd → 重试线上体检；失败自动回滚！）
uv run python scripts/ops/deploy_cloud.py

# 常用变体：
#   uv run python scripts/ops/deploy_cloud.py --backend-only         # 仅发后端
#   uv run python scripts/ops/deploy_cloud.py --site-only            # 仅发前端
#   uv run python scripts/ops/deploy_cloud.py --sync-mode patch      # 未 push 到 origin 时走 patch 同步
#   uv run python scripts/ops/deploy_cloud.py --site-build local     # 本机构建前端后 scp 原子替换
#   uv run python scripts/ops/deploy_cloud.py --with-sailtick        # 同步重启并体检 sailtick.service
```

#### ⑤ 线上回归与应急回滚（Regression & Rollback）

- 发布成功后，AI 向用户汇总：**变更内容、新旧 commit SHA、备份文件路径、`health_check.py --env prod` 全量通过报告**，交由人类在公网 Web / 手机 Android App 完成最终版本验收。
- 若线上体检失败，`deploy_cloud.py` 会**自动回滚代码至 `PREV_COMMIT`、恢复 `site_dist.prev`、重启服务并打印 `journalctl` 最近 40 行日志**。
- 如需手动回滚到任意历史版本：

```powershell
uv run python scripts/ops/deploy_cloud.py --rollback <PREV_COMMIT>
uv run python scripts/ops/health_check.py --env prod
```

---

## 5. 常见故障速查（Troubleshooting）

| 现象 | 常见原因 | 解决方案 |
|---|---|---|
| `ssh -v` 显示 `Server accepts key` 但随后 `Permission denied` | PowerShell 用 `-N '""'` 生成密钥时误将字面 `""` 设为口令 | 执行 `uv run python -c 'import subprocess, os; p = os.path.expanduser("~/.ssh/id_ed25519_sailzen"); subprocess.run(["ssh-keygen", "-p", "-P", "\"\"", "-N", "", "-f", p], check=True)'` 清空口令 |
| `doctor --check-remote` 偶发 SSH 超时 | 公网瞬时抖动或安全组延迟 | 先跑 `ssh -o BatchMode=yes sailzen-prod "echo ok"` 确认网络恢复后再重跑 |
| `deploy_cloud.py` 重启报 `sudo: a password is required` | 云端未配置 `sudoers` NOPASSWD | 按 §1.4 在云端 `/etc/sudoers.d/sailzen-ops` 为对应服务名配置免密 |
| `restore_local_db.py` 报 `安全拦截：目标数据库不是本机地址` | `.env.dev` 的 `POSTGRE_URI` 误填了云端 IP | 将 `.env.dev` 的 `POSTGRE_URI` 改回 `localhost:5432/main` |
| 找不到 `pg_dump` / `pg_restore` | PostgreSQL 与 pgAdmin 4 装在非默认路径 | 在 `.env.ops` 中显式填写 `OPS_PG_BIN_DIR=<实际bin目录>` |
| `backup_prod_db.py` 的 `direct` 模式耗时较长（如 98 MB 约 9 分钟） | `direct` 模式在客户端压缩，未压缩流走公网带宽 | 配好云端 `sudo -u postgres pg_dump` 免密后，在 `.env.ops` 改设 `OPS_BACKUP_MODE=ssh`（云端本地压缩后再 `scp` 拉回） |
| 还原后写入报 `duplicate key value violates unique constraint` | 序列未推进到最大 ID | `restore_local_db.py` 已内置全表序列修复；如手工导入过数据，重新跑一次 `restore_local_db.py` 即可 |
