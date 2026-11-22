---
name: sailzen-android-app-dev
description: |
  SailZen Android App（Kotlin + Jetpack Compose）全生命周期开发与发布技能。
  覆盖：应用架构与导航规范、Material 3 UI 重构与反模式红线（Edge-to-Edge / 防双倍 Insets / 顶栏与 Tab 布局 / 非阻塞错误处理）、
  初始化与 WebSocket 长连接稳定性、本地 Android Studio / Emulator + adb 截图与日志联调工作流、
  项目本地自签名证书与 versionCode 自动递增、云端 SCP OTA 一键发布，以及结合 SSH 云端日志的故障排查手册。
---

# SailZen Android App 开发、调试与 OTA 发布指南

本技能沉淀 SailZen Android 端（`android/`）的工程规范、UI 设计标准、本地模拟器实测方法与云端 OTA 发布闭环，适用于：
- 新增 Android 功能模块或重构现有页面 UI / 交互体验
- 排查连接异常、闪退、布局挤压、状态栏/底栏异常等客户端问题
- 本地构建、运行单元测试与 Android 模拟器真机级视觉验收
- 打包自签名 Release APK 并经 SCP 自动发布到云端触发手机 OTA 更新

关联文件：
- Android 工程：`android/app/build.gradle.kts`、`android/version.properties`、`android/app/src/main/AndroidManifest.xml`
- 本地签名配置（已 gitignore）：`android/keystore/sailzen-release.jks`、`android/keystore.properties`
- 发布与构建脚本：`scripts/ops/init_android_signing.py`、`scripts/ops/build_android_release.py`、`scripts/ops/publish_android_apk.py`
- 云端 OTA 分发接口：`sail_server/controller/app_release.py`、`sail_server/router/app_release.py`（`/api/v1/app/release/*`）
- 运维协作规范：`.agents/skills/sailzen-ops/SKILL.md`、`AGENTS.md`、`doc/maintain/DevOps.md`

---

## 0. 核心原则与不可逾越的红线

1. **凭据与签名零入库**：
   - `android/keystore/`、`*.jks`、`*.keystore`、`android/keystore.properties` 已全部在 `android/.gitignore` 排除，**严禁提交到 Git、严禁打入 patch、严禁在日志中打印 keystore 密码或 `SAILZEN_API_TOKEN`**。
   - **禁止覆盖已投入使用的自签名证书**（除非明确接受用户卸载重装），因为 Android 覆盖安装要求包名 + 签名指纹严格一致。
2. **Release 包必须先探活再打包**：
   - Release 构建会锁定 `BuildConfig.SERVER_URL`（`SERVER_URL_LOCKED=true`），一旦漏写端口号（如把 `:4399` 写成默认 80 端口），安装后用户在手机端无法修改，甚至连 OTA 自更新通道也会一起锁死。
   - 始终通过 `scripts/ops/publish_android_apk.py` 发布（内置 `/api/v1/health` 打包前可达性校验与 `version.properties` 失败自动回滚）。
3. **改完必跑单测 + 模拟器视觉实测**：
   - 任何涉及 UI 布局、导航、初始化、连接状态、权限/安装流程的修改，不能只靠代码编译通过就交付——必须跑通 `testDebugUnitTest`，并在本地 Android 模拟器实装运行、抓 `adb logcat` 与 `adb exec-out screencap -p` 检查真实渲染效果。
4. **Windows PowerShell (`pwsh`) 规范**：
   - 使用 `;` 分隔命令，不用 `&&`；Gradle 在 `android/` 目录用 `.\gradlew.bat`；Python 脚本统一用 `uv run`。

---

## 1. Android 工程架构与模块地图

### 1.1 导航与 5 个一级 Tab（`ui/navigation/NavGraph.kt`）

| 底栏 Tab | 路由常量 | 主界面 | 关联后端路由 |
|---|---|---|---|
| **规划** | `Routes.PLAN` | `feature/plan/PlanScreen.kt`（页内 Tab：今日 / 事务 / 事业） | `/api/v1/rhythm/*` |
| **收件箱** | `Routes.INBOX` | `feature/inbox/InboxScreen.kt`（待处理 / 历史） | `/api/v1/reminder/*` |
| **记账** | `Routes.MONEY` | `feature/money/MoneyScreen.kt` | `/api/v1/finance/*` |
| **健康** | `Routes.HEALTH` | `feature/health/HealthHomeScreen.kt` + 6 个健康子模块 + SailTick 教练页 | `/api/v1/health/*`, `/api/v1/tick/*` |
| **阅读** | `Routes.READER` | `feature/reader/ReaderHomeScreen.kt` → `ReaderScreen.kt` | `/api/v1/text/*` |

- **设置页**（`Routes.SETTINGS` → `feature/settings/SettingsScreen.kt`）：从任意一级 Tab 右上角齿轮图标进入，负责连接状态诊断、测试连接、Token/安静时段配置与手动检查 OTA 更新。
- **跨端代码生成联动**：修改 `config/body_metrics.toml` 后必须运行 `uv run python scripts/generate_body_metrics.py` 并通过 `--check`，确保 Android 身体指标定义与后端/Web 一致。

### 1.2 核心基础设施层（`core/`）

- `core/data/SettingsManager.kt`：DataStore 持久化配置（Server URL、API Token、Device ID、安静时段、同步游标、OTA 忽略版本号）。
- `core/data/DataChangeBus.kt`：跨页面领域事件总线（体重/身体数据/健康信号/事务变更后自动联动刷新）。
- `core/network/ApiClient.kt`：按 `(baseUrl, token)` 缓存各模块 Retrofit 实例，统一附加 `Authorization: Bearer <token>`；提供 `downloadClient(token)` 专用于大文件（APK 等）流式下载（120s 读超时）。
- `core/network/ReminderWebSocket.kt` + `core/bg/ReminderService.kt`：前台服务维持 WebSocket 长连接、断线指数退避重连、推送系统通知。
- `core/update/AppUpdateManager.kt` + `ui/components/AppUpdateDialog.kt`：云端 OTA 版本检查、断点友好流式下载、缓存复用、SHA-256 校验与 `FileProvider` 拉起系统安装器。

---

## 2. UI 设计与重构规范（踩坑沉淀清单）

开发新页面或改造旧页面时，**必须逐项遵守以下规范**：

### 2.1 Edge-to-Edge、状态栏与防双倍 WindowInsets

1. **状态栏图标可读性**：
   - `MainActivity.onCreate()` 必须在 `super.onCreate()` 前调用 `enableEdgeToEdge()`。
   - `res/values/themes.xml` 保持 `<item name="android:windowLightStatusBar">true</item>`，避免浅色主题下顶部时间/Wi-Fi/电量图标发白不可见。
2. **杜绝嵌套 `Scaffold` 双倍留白**：
   - 外层 `SailZenNavGraph` 的 `Scaffold` 只管理底部 `NavigationBar`，必须声明 `contentWindowInsets = WindowInsets(0, 0, 0, 0)`，并且 `NavHost` 仅使用 `Modifier.padding(bottom = padding.calculateBottomPadding())`。
   - 各一级 Tab 页内部的 `Scaffold` 同样声明 `contentWindowInsets = WindowInsets(0, 0, 0, 0)`，让各自的 `TopAppBar` 独立消费顶部状态栏高度。
3. **底栏显隐规则**：
   - 仅在 5 个一级 Tab（`PLAN` / `INBOX` / `MONEY` / `HEALTH` / `READER`）显示底部 `NavigationBar`；进入设置页或任何详情/二级子页时隐藏底栏。

### 2.2 顶栏（TopAppBar）、日期条与页内 Tab 布局

1. **`TopAppBar` 严禁塞入多行内容或过宽控件**：
   - Material 3 `TopAppBar` 默认高度仅 `64.dp`。禁止在 `title` 内放 `Column` + `48.dp` 按钮行 + 长 URL 文本，否则会垂直溢出并挤压下方的 `PrimaryTabRow`。
   - 正确布局层次（参考 `PlanScreen.kt`、`HealthHomeScreen.kt`）：
     1. **单行 `TopAppBar`**：简短页面标题（可附小巧状态胶囊，如 `● 已连接`）+ 右侧 1–3 个动作图标（所有一级 Tab 均应保留 `Settings` 图标）。
     2. **加载指示器**：刷新时在 `TopAppBar` 正下方展示 `2.dp` 高度的 `LinearProgressIndicator`，禁止在内容区左上角浮空叠放 `CircularProgressIndicator`。
     3. **独立日期切换条**：`< 2026-11-22 · 周日 今天 >` 独占一行（点击日期可一键回今天），下方以浅色 `HorizontalDivider` 分隔。
     4. **非侵入式状态/错误条**：仅在异常时展示紧凑提示条（带「重试 / 设置」动作），绝不挤压标题或 Tab。
     5. **页内 `PrimaryTabRow`**：标签简洁，计数徽标放在文字右侧留出 `4.dp` 间距，避免裁剪。

### 2.3 错误处理与离线体验（红线：严禁阻塞死循环）

1. **禁止用不可关闭的模态 `AlertDialog` 报网络/加载错误**：
   - 典型反模式：`AlertDialog(onDismissRequest = { viewModel.refresh() }, confirmButton = { TextButton(onClick = { viewModel.refresh() }) { Text("重试") } })` —— 断网时会彻底锁死底栏切换与返回键，把用户困在无限重试死循环中！
2. **正确错误反馈分层**：
   - **页面/看板加载失败**：在 `LazyColumn` 顶部展示**非阻塞错误卡片**（包含具体报错原因 + 「忽略 / 设置 / 重试」三个按钮），同时保留上次已加载的缓存数据不清空页面。
   - **写操作瞬态提示**（提交成功/失败、状态流转受限等）：统一使用 `Scaffold` 的 `SnackbarHost`，不弹打断式弹窗。
   - **确认型弹窗**（删除二次确认、破戒备注、新建表单、OTA 升级提示）：必须提供明确的关闭/取消入口与安全的 `onDismissRequest`。

### 2.4 信息展示质感标准

- **禁止裸露原始 JSON**：后端返回的 `JsonElement`（如 `HealthSignalItemDto.valueJson`）必须解析格式化为人类可读文本（如 `100.5 kg`、`30 分钟`），禁止直接 `.toString()` 渲染给用户。
- **使用语义图标与统一卡片组件**：列表项与入口卡片使用与业务匹配的 Material 图标（优先使用 `Icons.AutoMirrored.Filled.*` 消除废弃告警）；模块化入口优先复用带 `icon` / `subtitle` / `showChevron` 的 `ui/components/SectionCard.kt`，避免空白壳子卡片。

---

## 3. 初始化、配置锁定与长连接稳定性规范

1. **`SettingsManager` 地址解析规则**：
   - `BuildConfig.SERVER_URL_LOCKED == true`（Release 构建）且 `BuildConfig.SERVER_URL` 非空时，`serverUrl()` 与 `serverUrlFlow` **必须无条件返回 `BuildConfig.SERVER_URL`**，避免 Android AutoBackup 或旧版安装遗留的空白/旧 DataStore 值导致永久连不上。
   - Debug 构建下若 DataStore 未设置或为空字符串，回退到 `BuildConfig.SERVER_URL`。
2. **`ReminderService` 前台服务与重连**：
   - `SailZenApp.onCreate()` 与 `MainActivity.onStart()` 两处均调用 `ReminderService.ensureStarted()`，内部捕获 Android 12+ 后台拉起前台服务的 `ForegroundServiceStartNotAllowedException`，确保进入前台时 100% 拉起。
   - 配置变更或用户手动重连时，通过 `ReminderService.restart(context)` 发送 `ACTION_RECONNECT` Intent 在服务内原子停旧建新 `ReminderWebSocket`，**禁止** `stopService()` 紧跟 `startForegroundService()` 产生竞态。
   - `ReminderService` 对外暴露 `connectedState`、`connectionState`、`connectionDetail` 三个 `StateFlow`，便于规划页与设置页透出具体连接状态与错误码（如 `CONN_REFUSED`、`AUTH_FAILED`、`HTTP_404`）。
3. **设置页自诊断能力**：
   - 保留「测试连接」按钮（直连 `GET <baseUrl>/api/v1/health`，回显真实耗时或具体异常与完整请求 URL），方便真机现场 1 秒定位是端口、防火墙、网络还是 Token 问题。

---

## 4. 本地 Android Studio / 模拟器调试与视觉验收工作流

### 4.1 单元测试与编译门禁

```powershell
# 运行全部 JVM 单元测试（快速验证 ViewModel / Repository / AppUpdateManager 等）
cd android; .\gradlew.bat testDebugUnitTest

# 运行单个测试类
cd android; .\gradlew.bat testDebugUnitTest --tests "com.sailzen.app.core.update.AppUpdateManagerTest"

# 编译 Release 包（校验 Kotlin / LintVital / 资源优化 / 签名配置）
cd android; .\gradlew.bat assembleRelease
```

### 4.2 本地模拟器实装 + 截图视觉验收（AI 推荐标准流程）

1. **查看设备与可用 AVD**：
   ```powershell
   adb devices -l
   & "$env:LOCALAPPDATA\Android\Sdk\emulator\emulator.exe" -list-avds
   ```
2. **后台启动本地模拟器**（以 `Medium_Phone_API_36` 为例，使用 `IsDaemon=true` 启动）：
   ```powershell
   & "$env:LOCALAPPDATA\Android\Sdk\emulator\emulator.exe" -avd Medium_Phone_API_36 -no-audio -no-boot-anim -gpu swiftshader_indirect
   ```
   等待 `adb shell getprop sys.boot_completed` 返回 `1`。
3. **安装并启动最新 Release APK**：
   ```powershell
   $apk = (Get-ChildItem "android\app\build\outputs\apk\release\*.apk" | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
   # 同签名直接覆盖安装；若报 INSTALL_FAILED_UPDATE_INCOMPATIBLE（旧 debug 包冲突），先 adb uninstall com.sailzen.app
   adb install -r $apk
   adb shell pm grant com.sailzen.app android.permission.POST_NOTIFICATIONS
   adb logcat -c
   adb shell am start -n com.sailzen.app/.MainActivity
   ```
4. **抓日志与实拍截图检查**：
   ```powershell
   # 检查 WebSocket 握手与各仓库告警/崩溃日志
   adb logcat -d -s ReminderWebSocket:D ReminderService:D HealthRepository:W RhythmRepository:W AndroidRuntime:E

   # 截取当前屏幕（保存到对话 scratch 目录后用 read_file 肉眼检查像素）
   adb exec-out screencap -p > "<scratch_dir>\screen.png"

   # 模拟点击切换底栏 Tab（先 adb shell wm size 确认分辨率，1080x2400 下底栏 y≈2280，5 Tab x≈108/324/540/756/972）
   adb shell input tap 756 2280
   ```
5. **收尾关闭模拟器**（释放宿主机内存）：
   ```powershell
   adb emu kill
   ```

---

## 5. 自签名配置、版本管理与云端 OTA 一键发布

### 5.1 自签名证书初始化（每台开发机仅一次）

Android 所有 Release 包本质上都是 JDK `keytool` 生成的自签名证书。本项目采用**项目本地化方案**（均已 gitignore，无需修改 `~/`）：

```powershell
# 自动从 .env.prod / .env.ops 推导含端口的公网地址（如 http://101.43.22.254:4399），
# 生成 27 年自签名证书 android/keystore/sailzen-release.jks 与 android/keystore.properties
uv run python scripts/ops/init_android_signing.py

# 或显式指定公网地址（务必带真实监听端口！）
uv run python scripts/ops/init_android_signing.py --server-url http://101.43.22.254:4399
```

> **重要**：初始化完成后，请将 `android/keystore/sailzen-release.jks` 与 `android/keystore.properties` 备份到网盘/密码管理器。换电脑后只需还原这两个文件，即可继续无缝覆盖更新手机 App。

### 5.2 配置读取优先级（`build.gradle.kts` 与 `build_android_release.py` 一致）

1. Gradle 命令行 `-P` 参数 / 进程环境变量（最高）
2. `android/keystore.properties`（推荐：项目本地且已 gitignore）
3. `android/gradle.properties` / `~/.gradle/gradle.properties`（兜底兼容）
4. 键名同时兼容 `SAILZEN_RELEASE_*` 与 `SAILZEN_*` 前缀。

### 5.3 版本号管理（`android/version.properties`）

```properties
VERSION_CODE=1
VERSION_NAME=0.2.0
```

- `VERSION_CODE`：Android 覆盖升级与 OTA 更新判断的唯一依据（`remote.versionCode > BuildConfig.VERSION_CODE`），由 `publish_android_apk.py` 每次发布**自动 +1**；若构建或上传失败会自动回滚该文件。
- `VERSION_NAME`：面向人类展示的版本号，平时无需修改，大迭代时加 `--version-name 0.3.0` 即可。

### 5.4 一键打包与 SCP OTA 发布

```powershell
# 1. 先演练（校验签名、探活锁定地址 /api/v1/health、预览 latest.json，零副作用）
uv run python scripts/ops/publish_android_apk.py --dry-run

# 2. 正式发布（自动 versionCode+1 → assembleRelease → SHA-256 → SCP 原子上传 → 清理旧包保留 5 个 → 线上探活）
uv run python scripts/ops/publish_android_apk.py -m "本次更新说明（展示在手机更新弹窗）"

# 常用扩展参数：
#   --with-tests           打包前先跑 testDebugUnitTest
#   --version-name 0.3.0   同步升级 VERSION_NAME
#   --no-bump              不递增 VERSION_CODE（重传同一版本或首次基准包）
#   --apk <path>           跳过编译，直接发布已构建好的 APK
#   --keep 5               云端保留最近 N 个历史 APK（默认 5）
```

### 5.5 手机端 OTA 体验与边界

- **云端接口**：`GET /api/v1/app/release/latest`、`GET /api/v1/app/release/download/{filename}`、`GET /api/v1/app/release/latest.apk`（复用 `SAILZEN_API_TOKEN` Bearer 鉴权，文件存储在云端 `<SERVER_DATA_DIR>/app_releases/`）。
- **手机端触发**：App 启动时静默检查（支持“忽略此版本”），也可随时在 **设置 → 应用更新** 手动点「检查更新」→ 流式下载带进度条 → 本地 SHA-256 校验通过 → `FileProvider` 拉起系统原生安装器（首次需按引导在系统设置开启一次「允许安装未知应用」）。
- **何时仍需手动装一次**：仅在（1）首次从 debug 签名切换为自签名基准包（需先卸载旧版），或（2）旧版锁死了不可达的服务器地址/端口时，需要手动覆盖安装一次；之后全部迭代均可走 OTA。

---

## 6. 故障排查手册（客户端 + SSH 云端联调）

| 现象 | 优先排查路径 | 常见根因与解法 |
|---|---|---|
| **一直显示「未连接」** | 1. 手机「设置 → 测试连接」看具体报错与完整 URL<br>2. SSH 查云端实际监听端口：`ss -tlnp` 与 `systemctl list-units \| grep -iE 'sail\|server'`<br>3. 检查 `android/keystore.properties` 的 `SAILZEN_RELEASE_SERVER_URL`<br>4. 验证 WS 握手与 `SAILZEN_API_TOKEN` | 最常见：云端 `my-server.service` 实际监听在 `:4399`（无 80 反代），而 URL 漏写 `:4399`；或 Token 不匹配返回 401。修正 URL 后重新发布并通过新包覆盖安装。 |
| **安装报签名冲突 (`INSTALL_FAILED_UPDATE_INCOMPATIBLE`)** | 检查手机上原有包是 debug 签名还是旧 keystore | 先卸载手机上的旧版 SailZen，再安装当前自签名 Release 包；之后保持同一 `.jks` 即可覆盖安装。 |
| **手机检查更新提示“已是最新”或报 404** | 1. 浏览器/curl 请求 `GET <prod_url>/api/v1/app/release/latest`<br>2. SSH 检查云端 `<remote_repo>/data/app_releases/latest.json`<br>3. 检查 `sudo journalctl -u my-server.service -n 80 --no-pager` | 云端尚未部署包含 `/api/v1/app` 路由的新后端（先跑 `deploy_cloud.py --backend-only`）；或云端 `SERVER_DATA_DIR` 与 `OPS_REMOTE_APP_RELEASES_DIR` 路径不一致；或 `remote.version_code <= local.VERSION_CODE`。 |
| **下载完成点「立即安装」无反应** | 检查 `adb logcat -d -s AndroidRuntime:E` 与应用“安装未知应用”权限 | 确认 `AndroidManifest.xml` 中 `REQUEST_INSTALL_PACKAGES` 与 `FileProvider`（`res/xml/file_paths.xml` 映射 `cache-path path="updates/"`）完好，并在系统设置授予安装未知应用权限。 |
| **某页面数据加载失败 / 接口 4xx/5xx** | 同时抓取本机 `adb logcat` 与云端 `sudo journalctl -u my-server.service -n 100 --no-pager` 对比请求路径与参数 | 检查 DTO 字段是否与服务端最新 Schema 漂移、是否缺少必填 Query 参数、或 `SAILZEN_API_TOKEN` 鉴权头缺失。 |
| **Android 模拟器截图顶部状态栏看不见或留白过大** | 用 `adb exec-out screencap -p` 实拍检查 | 检查 `MainActivity` 是否调用 `enableEdgeToEdge()`、`themes.xml` 是否含 `windowLightStatusBar=true`、以及内外层 `Scaffold` 是否重复应用 `WindowInsets`。 |

### 一键 SSH 云端诊断命令模板（只读安全）

```powershell
uv run python -c "
from scripts.ops.common import load_ops_config, run_ssh_command
cfg = load_ops_config()
cmd = '''
ss -tlnp | grep -E '4399|1974|9070|80|443' || true
systemctl is-active my-server.service sailtick.service || true
ls -la /home/ubuntu/repos/SailZen/data/app_releases/ 2>/dev/null || true
sudo journalctl -u my-server.service -n 60 --no-pager || true
'''
print(run_ssh_command(cfg, cmd, check=False, timeout=30).stdout)
"
```

---

## 7. 每次 Android 迭代的验收清单（Definition of Done）

- [ ] **代码规范**：无新增阻塞式加载错误弹窗；无裸露原始 JSON；无废弃图标/API 告警；一级页面均带设置入口且 Insets 正常。
- [ ] **单测门禁**：`cd android; .\gradlew.bat testDebugUnitTest` 全部通过；如改了后端/运维脚本，同步跑通 `uv run pytest tests/server/test_app_release_api.py tests/server/test_router_mount.py tests/unit/test_ops_scripts.py`；如改了 `config/body_metrics.toml`，通过 `generate_body_metrics.py --check`。
- [ ] **模拟器实测**：安装 Release 包到本机模拟器验证 WS 握手成功、主页面渲染无挤压/遮挡、核心交互无崩溃，验收后 `adb emu kill`。
- [ ] **安全发布**：先 `publish_android_apk.py --dry-run` 确认护栏与 `/api/v1/health` 探活通过，再执行 `publish_android_apk.py -m "..."` 发布上云，确认 `latest.json` 探活一致。
- [ ] **Git 合规**：确认 `git status --short` 不包含 `android/keystore/`、`android/keystore.properties`、`*.jks` 或 `.env.*`，按 `commit-current-change` / `finalize-today-work` 规范提交交付。
