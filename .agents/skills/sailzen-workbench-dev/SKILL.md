---
name: sailzen-workbench-dev
description: |
  SailZen VS Code 工作台插件（packages/sailzen-workbench/，TypeScript + esbuild + VS Code API）全生命周期开发、测试与云端 OTA 发布运维技能。
  覆盖：单扩展轻量架构与模块地图、8,500+ 篇点层级 Markdown 极速索引与原子改链规范、双库隐私防火墙（PrivacyGuard）与多机器语义/路径分离（~/.sailzen/machine.json）、
  后端 /api/v1/workbench/* 联调与降级机制、TypeScript/Jest/VSIX 本地构建与零警告打包、
  云端 SCP VSIX OTA 一键发版（scripts/ops/publish_vscode_vsix.py）与无 JS 环境轻量笔记本一键自更新闭环，以及常见运维故障速查手册。
---

# SailZen VS Code Workbench 开发、运维与云端 OTA 发布指南

本技能沉淀新版 SailZen VS Code 工作台插件（`packages/sailzen-workbench/`，已彻底替代归档于 `archive/dendron_legacy/` 的旧 8 包 Dendron 体系）的开发规范、测试门禁、多机器配置、云端 VSIX OTA 发版与故障排查闭环。

适用场景：
- 迭代工作台功能（Vault 笔记引擎、Rhythm v2 / SailTick、Content 2.0 虚拟图书馆/围栏同步、四大创作与工程工作流）
- 修改后端 `/api/v1/workbench/*` 或 `/api/v1/text/edition/{id}/chapter-sync` 适配接口
- 本地类型检查、Jest 单元测试、esbuild 打包与无警告 `.vsix` 构建
- 通过 `scripts/ops/publish_vscode_vsix.py` 一键递增版本号并将 VSIX 原子发布到云服务器，驱动多台机器（含无 Node.js/pnpm 环境的轻量笔记本）完成 OTA 自更新
- 排查连接、配置优先级、快捷键冲突、SSH 限流与远端构建锁文件失配等问题

关联文件：
- 扩展工程：`packages/sailzen-workbench/package.json`、`esbuild.config.mjs`、`tsconfig.json`、`jest.config.cjs`、`README.md`、`LICENSE`
- 扩展设计文档：`doc/design/vscode_plugin/workbench-refactor.md`
- 后端聚合与 OTA 路由：`sail_server/router/workbench.py`、`sail_server/controller/workbench.py`、`sail_server/model/workbench.py`、`sail_server/application/dto/workbench.py`、`sail_server/config/paths.py`
- 云端 VSIX 发布脚本：`scripts/ops/publish_vscode_vsix.py`、`scripts/ops/common.py`、`scripts/ops/health_check.py`
- 运维协作规范：`.agents/skills/sailzen-ops/SKILL.md`、`AGENTS.md`

---

## 0. 核心原则与不可逾越的红线

1. **工作库强制离线隔离（`PrivacyGuard` 硬不变量）**：
   - 任何归属 `work` Vault（或 `cloudSync: false`）的文件与上下文，**严禁**向个人云端 `sail_server` 发送笔记正文、标题、路径、任务、快聊或 AI 抽取请求。
   - 所有新增外发写/同步 API 必须在 `SailZenApiClient` 内调用 `this.privacyGuard.assertCloudUploadAllowed(action, sourceFsPath)`。
2. **多机器「语义 vs 物理路径」严格解耦**：
   - 云端 `RhythmAffair.kind_meta.workbench` 仅允许存储跨机器语义标识（`slug / archetype / vault_namespace / repo_hints / topic_id / original_work_id`），**严禁写入任何盘符、反斜杠或本机绝对路径**（后端 Pydantic 校验器强制拦截）。
   - 本机 Vault 路径、项目仓库路径、Pin 书单与 Token 仅存于本机 `~/.sailzen/machine.json`，绝不入 Git、绝不入云端数据库。
3. **零破坏存量 `D:/vault` 笔记（8,500+ 篇）**：
   - 保持 100% Dendron 点层级 `.md` 与 YAML frontmatter 兼容（含折叠标题 `>-`、`traitIds`、`templates.daily.md` 的 `{{ getDayOfWeek (fnameToDate) }}`）。
   - 重命名/批量重命名/层级重构必须经 `vscode.WorkspaceEdit` 原子提交（支持 `Ctrl+Z` 撤销）；删除必须走 `useTrash: true` 移入系统回收站；日记/读书卡回写仅更新受控围栏（`<!-- sailzen:rhythm:start/end -->`、`<!-- sailzen:managed:meta:start/end -->`），绝不覆盖手写内容。
4. **保持极简单扩展体积（反臃肿红线）**：
   - 严禁重新引入 Prisma、本地 Express (`api_server`)、`unified/remark` 重管线或废弃的 `archive/dendron_legacy/` 任何包；扩展依赖保持极简（当前仅 `js-yaml`），生产 bundle 维持轻量秒级打包。
5. **Windows PowerShell (`pwsh`) 规范**：
   - 用 `;` 分隔命令，不用 `&&`；Python 脚本统一走 `uv run`，前端/扩展统一走 `pnpm`。

---

## 1. 架构与模块地图

```text
packages/sailzen-workbench/
├── package.json                       # 扩展 manifest（命令、菜单、Dendron 一致快捷键、配置项）
├── esbuild.config.mjs                 # 单文件 CJS 打包 dist/extension.js (~146KB, ~20ms)
├── README.md / LICENSE / .vscodeignore# 零警告 vsce 打包必备资产（README 含 Release Notes）
├── src/
│   ├── extension.ts                   # 激活入口：注册 VFS/Tree/Webview/Provider/命令 + 4.5s 后静默 OTA 检查
│   ├── core/
│   │   ├── vault/                     # 纯 Node 零 vscode 依赖（可直接 Jest 压测）
│   │   │   ├── noteModel.ts           # YAML frontmatter + 精确偏移 [[wikilink]] 解析（跳过代码块）
│   │   │   ├── cacheStore.ts          # .sailzen-index.json 暖缓存
│   │   │   ├── vaultIndex.ts          # 内存 Trie + 增量校验 + 模糊检索 + 原子单篇/批量/层级改链计划
│   │   │   └── templateEngine.ts      # 日记命名与 templates.daily.md 模板渲染
│   │   ├── machine/
│   │   │   ├── machineConfig.ts       # ~/.sailzen/machine.json 读写、双库、projectPaths、pinnedWorkIds
│   │   │   └── privacyGuard.ts        # 工作库离线防火墙（PrivacyViolationError）
│   │   ├── server/
│   │   │   ├── types.ts               # 对齐 sail_server 的强类型 DTO
│   │   │   ├── apiClient.ts           # REST 客户端（15s 超时、Bearer 鉴权、bootstrap 404 平滑降级）
│   │   │   ├── virtualFs.ts           # sailzen:// 只读虚拟文件系统（章节/Clips/NoteItem/Topic）
│   │   │   ├── fencedSync.ts          # read.*/topic.*/study.* 围栏式双向同步
│   │   │   └── updater.ts             # Semver 比较 + VSIX 下载 + SHA-256 强校验
│   │   └── workbenchState.ts          # 全局状态、暖缓存非阻塞启动、Watcher、WorkspaceEdit、Trash 删除
│   └── features/
│       ├── editor/
│       │   ├── wikilinkProvider.ts    # [[wikilink]] 补全/跳转/建壳/悬浮（含云端 Story Bible）+ repo:// 跳转
│       │   └── journalBridge.ts       # 日记 ↔ Rhythm 围栏同步
│       ├── views/                     # Rhythm / QuickChat / Projects & Content / Vault Tree / Calendar / StatusBar
│       ├── workflows/                 # novelWorkflow / projectWorkflow / contextPacker
│       └── commands/registerCommands.ts
└── tests/                             # 6 套 Jest 单元测试（纯 Node，毫秒级执行）
```

### 后端协作端点（`sail_server`）

| 端点 | 用途 | 所在模块 |
|---|---|---|
| `GET /api/v1/workbench/bootstrap?date=` | 单次 RTT 聚合今日时间线 + 活跃 Venture（含语义配置）+ Topic + 待处理票据 | `controller/workbench.py` |
| `PUT /api/v1/workbench/project/{venture_id}` | 强校验更新 Venture 跨机器语义元数据（拒绝盘符/绝对路径） | `controller/workbench.py` |
| `GET /api/v1/workbench/context-pack/{venture_id}` | 聚合项目倒排、里程碑、近期时间块、关联书单与 NoteItem | `controller/workbench.py` |
| `PUT /api/v1/text/edition/{edition_id}/chapter-sync` | 原创作品单章按 `source_slug` 幂等创建/更新并重算字数 | `controller/text.py` |
| `GET /api/v1/workbench/release/latest` | 查询最新云端 VSIX 元数据（`version / sha256 / download_path / release_notes`） | `controller/workbench.py` |
| `GET /api/v1/workbench/release/latest.vsix` | 流式下载最新 `.vsix`（供新机器首装或 OTA 下载） | `controller/workbench.py` |
| `GET /api/v1/workbench/release/download/{filename}` | 按安全文件名流式下载指定 `.vsix` | `controller/workbench.py` |

---

## 2. 本地开发、测试与打包工作流

### 2.1 日常开发与验证门禁

```powershell
# 1. TypeScript 严格类型检查
pnpm --filter=sailzen-workbench run typecheck

# 2. 运行全部单元测试（或从根运行 pnpm run test:workbench）
pnpm --filter=sailzen-workbench run test

# 3. 本地构建 / 监听热编译
pnpm run build-workbench
pnpm --filter=sailzen-workbench run watch

# 4. 本地零警告打 VSIX 包（用于本机离线测试安装）
pnpm run package-workbench
code --install-extension packages/sailzen-workbench/sailzen-workbench-X.Y.Z.vsix

# 5. 若同时改了后端 /api/v1/workbench/*，必跑后端 + 路由 + ops 护栏单测
uv run pytest tests/server/test_router_mount.py tests/server/test_workbench_api.py tests/unit/test_ops_scripts.py -v
```

### 2.2 本机配置（`~/.sailzen/machine.json`）

每台机器独立维护一份配置（Windows：`C:\Users\<user>\.sailzen\machine.json`；macOS/Linux：`~/.sailzen/machine.json`），在 VS Code 中执行 **`SailZen: Open Machine Config`** 即可打开：

```json
{
  "version": 1,
  "machineId": "home-win",
  "role": "dev-and-creation",
  "serverUrl": "https://your-sailzen-host:port",
  "apiToken": "可选，若服务端开启 SAILZEN_API_TOKEN",
  "activeVault": "private",
  "vaults": {
    "private": { "path": "D:/vault", "notesDir": "notes", "cloudSync": true },
    "work": { "path": "E:/work-vault", "notesDir": "notes", "cloudSync": false }
  },
  "projectPaths": {
    "sailzen": "F:/repos/myrepo/SailZen"
  },
  "pinnedWorkIds": []
}
```

- **配置优先级**：`~/.sailzen/machine.json` 的 `serverUrl` > VS Code Settings `sailzen.server.baseUrl` > 兜底 `http://localhost:1974`。
- **热生效**：修改保存 `machine.json` 后，点击侧边栏 **Refresh（`SailZen: Refresh Rhythm & Projects`）** 立即热重载，无需重启 VS Code。

---

## 3. 云端 VSIX OTA 发版与多机同步 SOP

> 与 Android APK OTA（`scripts/ops/publish_android_apk.py`）同构，云端存储目录默认 `<SERVER_DATA_DIR>/vscode_releases/`（可用 `.env.prod` 的 `VSCODE_RELEASES_PATH` 或 `.env.ops` 的 `OPS_REMOTE_VSCODE_RELEASES_DIR` 覆写）。

### 3.1 开发机标准发版步骤

1. **（可选）更新 Release Notes**：在 `packages/sailzen-workbench/README.md` 顶部 `## Release Notes` 补充本版说明（会在 VS Code 扩展详情页直接展示）。
2. **先做零副作用演练**：
   ```powershell
   uv run python scripts/ops/publish_vscode_vsix.py --dry-run -m "本次更新说明"
   ```
3. **正式一键构建、测试并原子发布上云**（默认自动递增 patch 版本号 `X.Y.Z -> X.Y.(Z+1)`；任何阶段失败均自动回滚 `package.json`）：
   ```powershell
   # 常规补丁版发布（推荐）
   uv run python scripts/ops/publish_vscode_vsix.py -m "本次更新说明"

   # 指定次版本或显式版本号
   uv run python scripts/ops/publish_vscode_vsix.py --bump minor -m "大功能里程碑"
   uv run python scripts/ops/publish_vscode_vsix.py --version 0.4.0 -m "版本说明"

   # 重传当前版本（不递增版本号）或直接上传已有 .vsix
   uv run python scripts/ops/publish_vscode_vsix.py --no-bump --vsix packages/sailzen-workbench/sailzen-workbench-0.3.1.vsix -m "重传说明"
   ```
4. **脚本自动完成的闭环**：
   - `typecheck` → `jest` → `vsce package`（零警告）→ 计算 SHA-256
   - 合并为 **3 次 SSH/SCP 连接**（带 `exit=255` 退避重试）：`mkdir -p` → `scp *.vsix.part` → 单次 SSH 原子 `mv` VSIX + base64 写 `latest.json` + 保留最近 5 个历史包
   - 自动探活 `GET /api/v1/workbench/release/latest` 校验线上版本号与 SHA-256 一致

### 3.2 其他机器（含无 Node.js/pnpm 轻量笔记本）更新与新机首装

- **已安装 ≥ `0.3.0` OTA 版的机器**：
  - 打开 VS Code 约 4.5 秒后自动静默检查，或手动执行命令 **`SailZen: Check for Workbench Update (OTA)`**。
  - 弹窗点击 **`Update & Reload`** → 插件内置下载器自动拉取 `.vsix` → **校验 SHA-256** → 调用 VS Code 官方内置命令 `workbench.extensions.installExtension` 原地安装 → 点击 **`Reload Now`**。
  - **完全不依赖目标机器安装 Node.js、pnpm 或 `code` CLI**。
  - 升级后执行 **`SailZen: Workbench Diagnostics`** 核对首行 `Extension Version: vX.Y.Z`。
- **全新空白机器首次安装**：
  - 未配置 `SAILZEN_API_TOKEN`：浏览器直接访问 `https://<云端地址>/api/v1/workbench/release/latest.vsix` 下载，在 VS Code 扩展栏 `...` → **Install from VSIX...** 安装。
  - 已配置 `SAILZEN_API_TOKEN`：
    ```powershell
    Invoke-WebRequest -Uri "https://<云端地址>/api/v1/workbench/release/latest.vsix" `
      -Headers @{ Authorization = "Bearer <TOKEN>" } `
      -OutFile sailzen-workbench-latest.vsix
    code --install-extension .\sailzen-workbench-latest.vsix
    ```

---

## 4. 后端联动发布检查清单

若本轮同时改动了 `sail_server/`（如新增 Workbench API 字段或修改 `pnpm-workspace.yaml`）：
1. 按 `.agents/skills/sailzen-ops/SKILL.md` 先执行 `uv run python scripts/ops/deploy_cloud.py --dry-run` 再正式部署后端与 Web 前端。
2. 运行只读线上体检确认含 `/api/v1/workbench/bootstrap` 全绿：
   ```powershell
   uv run python scripts/ops/health_check.py --env prod
   ```
3. 再执行 `publish_vscode_vsix.py` 发布新版插件 VSIX。

---

## 5. 常见故障与排障速查

| 现象 | 根因 | 处理方式 |
|---|---|---|
| `publish_vscode_vsix.py` 报 `Connection closed ... port 22 (exit=255)` | 云主机 `sshd` 短时高频连接限流（`MaxStartups`） | 已在脚本内合并为 3 次连接并带 3 次退避重试；若仍偶发，等待 5 秒后重试 `--no-bump --vsix ...` |
| `deploy_cloud.py` 远端前端构建报 `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH` | 本仓 `.gitignore` 忽略 `pnpm-lock.yaml`，云端留有旧 lockfile；`CI=true` 下 `pnpm install` 默认强制 frozen | 已在 `scripts/ops/deploy_cloud.py` 将回退分支显式写为 `--no-frozen-lockfile`（受 `tests/unit/test_ops_scripts.py` 回归保护） |
| 改了 VS Code Settings `sailzen.server.baseUrl` 却仍连 `localhost:1974` | `~/.sailzen/machine.json` 里显式写了 `"serverUrl": "http://localhost:1974"`（优先级更高） | 运行 `SailZen: Open Machine Config` 改 `machine.json` 的 `serverUrl`，保存后点侧边栏 Refresh 热生效 |
| `Ctrl+L` / `Ctrl+Shift+I` / `Ctrl+Shift+D` 未触发新版命令 | 本机仍同时启用着旧版 Dendron 插件（`sail-zen-vscode`）抢占快捷键 | 在 VS Code 扩展栏禁用或卸载旧版 `SailZen (sail-zen-vscode)`，仅保留新版 `SailZen Workbench` |
| 启动时未弹 OTA 更新提示 | ① 当前处于工作库离线模式（`🔒 Work (Offline)` 主动禁用外发）；② `sailzen.updater.checkOnStartup` 为 `false`；③ 云端尚未发过任何 VSIX（404） | 切回 Private Vault，运行 `SailZen: Check for Workbench Update (OTA)` 查看具体状态 |
| `vsce package` 弹出交互式 `[y/N]` 警告 | 缺少 `package.json` 的 `repository` 或根目录 `LICENSE` 文件 | 确保 `packages/sailzen-workbench/package.json` 保留 `repository` 且存在 `LICENSE` 与 `README.md` |
