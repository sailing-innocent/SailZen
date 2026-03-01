# SailZen Android 客户端设计方案

## 文档信息

- **版本**: 1.0
- **日期**: 2026-03-01
- **状态**: 设计阶段
- **作者**: AI Agent

---

## 1. 项目背景与目标

### 1.1 现状分析

SailZen 目前已有：
- **sail_server**: Python + Litestar 后端 API
- **packages/site**: React + TypeScript Web 前端
- **文本分析系统**: LLM 驱动的作品分析、人物档案、设定管理、大纲提取

### 1.2 浏览器端 LLM 交互痛点

| 痛点 | 描述 | 影响 |
|------|------|------|
| **网络限制** | 浏览器 CORS 策略、企业防火墙限制 LLM API 调用 | 无法直接调用外部 LLM |
| **移动端体验** | Web 端在移动设备上交互受限 | 操作不便、性能受限 |
| **后台处理** | 页面关闭后分析任务中断 | 长时间分析不可靠 |
| **离线能力** | 无法离线阅读和分析 | 网络不稳定时不可用 |
| **系统集成** | 无法使用系统级分享、推送等功能 | 用户体验割裂 |

### 1.3 Android 端目标

1. **绕过浏览器限制**: 原生 HTTP 客户端直接调用 LLM API
2. **优化移动体验**: 原生 UI 组件，适配手机屏幕
3. **后台任务支持**: 分析任务可在 App 后台继续运行
4. **离线能力**: 本地缓存章节内容，支持离线阅读
5. **系统整合**: 分享、推送、快捷操作等系统级集成

---

## 2. 技术选型

### 2.1 方案对比

| 方案 | 技术栈 | 优点 | 缺点 | 推荐度 |
|------|--------|------|------|--------|
| **原生 Kotlin** | Kotlin + Jetpack Compose | 性能最佳、完整系统访问、官方支持 | 开发成本高、需要 Android 知识 | ⭐⭐⭐⭐⭐ |
| **React Native** | React Native + TypeScript | 复用现有团队技术栈、跨平台 | 性能略差、LLM 相关库生态弱 | ⭐⭐⭐ |
| **Flutter** | Dart + Flutter | 跨平台、性能接近原生 | 需要学习 Dart、与现有 TS 生态不兼容 | ⭐⭐⭐⭐ |

### 2.2 推荐方案: 原生 Kotlin + Jetpack Compose

**选择理由:**
1. **LLM 调用优势**: 原生 HTTP 客户端无 CORS 限制，可直接调用 Moonshot/OpenAI/Gemini
2. **后台服务**: WorkManager 支持可靠的后台任务执行
3. **本地存储**: Room 数据库提供完整的离线数据支持
4. **团队成长**: 与现有 TypeScript/Python 技术栈形成互补
5. **长期维护**: Android 官方推荐，文档完善

### 2.3 技术架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         表现层 (UI Layer)                            │
├─────────────────────────────────────────────────────────────────────┤
│  Jetpack Compose                                                    │
│  ├── 页面: 作品列表、章节阅读、任务管理、人物档案                      │
│  ├── 组件: 文本选择器、进度指示器、对话气泡                           │
│  └── 主题: Material Design 3 + 自定义 SailZen 主题                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        业务逻辑层 (ViewModel)                        │
├─────────────────────────────────────────────────────────────────────┤
│  ├── 作品管理: WorkViewModel                                        │
│  ├── 分析任务: AnalysisTaskViewModel                                │
│  ├── 阅读器: ReaderViewModel                                        │
│  └── 设置: SettingsViewModel                                        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        数据层 (Data Layer)                           │
├─────────────────────────────────────────────────────────────────────┤
│  Repository Pattern                                                 │
│  ├── 网络数据源: Retrofit + OkHttp                                  │
│  │   ├── sail_server API (/api/v1/*)                                │
│  │   └── LLM API (Moonshot/OpenAI/Gemini)                           │
│  ├── 本地数据源: Room Database                                       │
│  │   ├── 章节缓存 (ChapterCache)                                    │
│  │   ├── 分析结果 (AnalysisResult)                                  │
│  │   └── 阅读进度 (ReadingProgress)                                 │
│  └── 数据同步: SyncManager                                          │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        基础服务层 (Services)                         │
├─────────────────────────────────────────────────────────────────────┤
│  ├── 后台任务: WorkManager (分析任务)                                │
│  ├── 推送通知: Firebase Cloud Messaging                             │
│  ├── 数据存储: DataStore (用户偏好设置)                              │
│  └── 网络监听: ConnectivityManager                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心功能模块

### 3.1 功能优先级

| 模块 | 功能 | 优先级 | 说明 |
|------|------|--------|------|
| **文本阅读** | 章节列表、阅读器、书签 | P0 | 核心基础功能 |
| **LLM 对话** | 直接调用 LLM API 进行分析 | P0 | 解决浏览器限制痛点 |
| **分析任务** | 创建/监控/接收通知 | P1 | 后台处理支持 |
| **人物档案** | 查看/编辑人物信息 | P1 | 数据浏览功能 |
| **设定管理** | 查看/编辑设定 | P1 | 数据浏览功能 |
| **大纲浏览** | 树形大纲展示 | P2 | 辅助功能 |
| **离线同步** | 章节下载/更新 | P2 | 增强体验 |
| **其他模块** | 财务/健康/项目 | P3 | 后续迭代 |

### 3.2 模块详细设计

#### 3.2.1 文本阅读模块

```kotlin
// 核心类设计
class ReaderViewModel(
    private val chapterRepository: ChapterRepository,
    private val settingsRepository: SettingsRepository
) : ViewModel() {
    
    // 章节内容流
    val chapterContent: StateFlow<ChapterContent> = ...
    
    // 阅读进度
    val readingProgress: StateFlow<ReadingProgress> = ...
    
    // 加载章节（优先本地缓存）
    fun loadChapter(editionId: Int, chapterIndex: Int)
    
    // 保存阅读进度
    fun saveProgress(position: Int)
    
    // 语音朗读（TTS）
    fun startTTS()
}

// UI 组件
@Composable
fun ReaderScreen(
    viewModel: ReaderViewModel = hiltViewModel()
) {
    // 沉浸式阅读界面
    // 支持手势翻页、字体调整、主题切换
}
```

**功能特性:**
- 竖向滚动阅读（类似微信读书）
- 字体大小/行间距调整
- 日间/夜间/护眼主题
- 阅读进度同步到后端
- TTS 语音朗读

#### 3.2.2 LLM 对话模块

```kotlin
// LLM 服务接口
interface LLMService {
    suspend fun complete(
        messages: List<Message>,
        config: LLMConfig
    ): Result<LLMResponse>
    
    suspend fun streamComplete(
        messages: List<Message>,
        config: LLMConfig
    ): Flow<LLMStreamChunk>
}

// 分析对话 ViewModel
class AnalysisChatViewModel(
    private val llmService: LLMService,
    private val analysisRepository: AnalysisRepository
) : ViewModel() {
    
    // 对话历史
    val messages: StateFlow<List<ChatMessage>> = ...
    
    // 发送分析请求
    fun sendAnalysisRequest(
        textRange: TextRangeSelection,
        analysisType: AnalysisType
    )
    
    // 流式接收响应
    private fun streamResponse(requestId: String)
}

// 对话界面
@Composable
fun AnalysisChatScreen(
    viewModel: AnalysisChatViewModel = hiltViewModel()
) {
    // 类似 ChatGPT App 的对话界面
    // 支持代码块、Markdown 渲染
}
```

**功能特性:**
- 直接调用 Moonshot/OpenAI/Gemini API
- 流式响应展示（打字机效果）
- 上下文管理（选择文本范围作为 context）
- 提示词模板选择（大纲提取、人物分析等）
- 历史对话保存

#### 3.2.3 后台分析任务模块

```kotlin
// 分析任务 Worker
class AnalysisTaskWorker(
    context: Context,
    params: WorkerParameters,
    private val analysisService: AnalysisService
) : CoroutineWorker(context, params) {
    
    override suspend fun doWork(): Result {
        // 执行长时间分析任务
        // 支持进度更新和断点续传
    }
}

// 任务调度
class AnalysisTaskScheduler(
    private val workManager: WorkManager
) {
    fun scheduleAnalysisTask(
        taskRequest: AnalysisTaskRequest,
        constraints: Constraints = defaultConstraints
    ): UUID {
        val workRequest = OneTimeWorkRequestBuilder<AnalysisTaskWorker>()
            .setInputData(taskRequest.toData())
            .setConstraints(constraints)
            .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
            .build()
        
        workManager.enqueue(workRequest)
        return workRequest.id
    }
}

// 进度监控
@Composable
fun TaskMonitorScreen(
    viewModel: TaskViewModel = hiltViewModel()
) {
    // 展示运行中的任务列表
    // 实时进度条
    // 任务完成通知
}
```

**功能特性:**
- 创建分析任务（大纲提取、人物检测等）
- 后台执行，App 关闭后继续运行
- 进度实时推送（Notification + 界面更新）
- 任务完成通知（系统通知栏）
- 断点续传（网络中断后自动恢复）

---

## 4. 数据同步策略

### 4.1 同步架构

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│   Android App   │ ◄─────► │  sail_server    │ ◄─────► │   PostgreSQL    │
│                 │  HTTP   │                 │  SQL    │                 │
├─────────────────┤         ├─────────────────┤         ├─────────────────┤
│ Room Database   │         │ Litestar API    │         │ 主数据库         │
│ (本地缓存)       │         │ (/api/v1/*)     │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

### 4.2 数据分类处理

| 数据类型 | 存储策略 | 同步时机 | 冲突解决 |
|----------|----------|----------|----------|
| **章节内容** | 本地优先 + 服务端备份 | 阅读时按需同步 | 服务端为准 |
| **阅读进度** | 本地 + 服务端 | 实时同步 | 时间戳最新为准 |
| **分析结果** | 服务端为主 + 本地缓存 | 查看时同步 | 服务端为准 |
| **分析任务** | 服务端主控 | 实时同步 | 服务端为准 |
| **用户设置** | 本地 + 云端备份 | 变更时同步 | 用户选择 |

### 4.3 离线优先策略

```kotlin
// Repository 示例
class ChapterRepository(
    private val localDataSource: ChapterLocalDataSource,
    private val remoteDataSource: ChapterRemoteDataSource,
    private val connectivityManager: ConnectivityManager
) {
    suspend fun getChapter(editionId: Int, chapterIndex: Int): Chapter {
        // 1. 先尝试从本地获取
        val localChapter = localDataSource.getChapter(editionId, chapterIndex)
        
        // 2. 如果有网络，检查更新
        if (connectivityManager.isOnline()) {
            try {
                val remoteChapter = remoteDataSource.getChapter(editionId, chapterIndex)
                // 更新本地缓存
                localDataSource.saveChapter(remoteChapter)
                return remoteChapter
            } catch (e: Exception) {
                // 网络错误，使用本地数据
                return localChapter ?: throw e
            }
        }
        
        // 3. 离线状态，返回本地数据
        return localChapter ?: throw OfflineException()
    }
}
```

---

## 5. API 接口适配

### 5.1 复用现有 API

Android 端将复用 sail_server 的现有 API：

| 端点 | 用途 | Android 端使用场景 |
|------|------|-------------------|
| `GET /api/v1/text/works` | 获取作品列表 | 首页作品列表 |
| `GET /api/v1/text/edition/{id}/chapters` | 获取章节列表 | 目录页面 |
| `POST /api/v1/analysis/range/content` | 获取文本内容 | 阅读器加载内容 |
| `POST /api/v1/analysis/task` | 创建分析任务 | 分析工作台 |
| `GET /api/v1/analysis/task/{id}` | 获取任务状态 | 任务监控 |
| `GET /api/v1/analysis/character/edition/{id}` | 获取人物列表 | 人物管理页 |

### 5.2 新增接口建议

为支持 Android 端推送通知等功能，建议后端新增：

```python
# 推送 token 注册
@post("/device/register")
async def register_device(
    device_token: str,           # FCM token
    device_type: str,            # "android" | "ios"
    user_preferences: dict,      # 用户偏好设置
)

# 分析任务完成时，由后端触发推送
# 复用现有任务系统，添加推送逻辑
```

---

## 6. 项目结构

```
packages/android/                    # Android 项目目录
├── app/
│   ├── src/main/
│   │   ├── java/com/sailzen/android/
│   │   │   ├── SailZenApplication.kt          # Application 类
│   │   │   ├── di/                            # 依赖注入 (Hilt)
│   │   │   │   ├── AppModule.kt
│   │   │   │   └── NetworkModule.kt
│   │   │   ├── data/                          # 数据层
│   │   │   │   ├── local/                     # Room 数据库
│   │   │   │   │   ├── dao/
│   │   │   │   │   ├── entity/
│   │   │   │   │   └── SailZenDatabase.kt
│   │   │   │   ├── remote/                    # 网络 API
│   │   │   │   │   ├── api/                   # Retrofit 接口
│   │   │   │   │   ├── dto/                   # 数据传输对象
│   │   │   │   │   └── llm/                   # LLM 服务
│   │   │   │   ├── repository/                # Repository 实现
│   │   │   │   └── sync/                      # 数据同步
│   │   │   ├── domain/                        # 领域层 (可选)
│   │   │   │   ├── model/                     # 领域模型
│   │   │   │   └── usecase/                   # 用例
│   │   │   ├── ui/                            # UI 层
│   │   │   │   ├── theme/                     # Compose 主题
│   │   │   │   ├── components/                # 共享组件
│   │   │   │   ├── reader/                    # 阅读器模块
│   │   │   │   ├── analysis/                  # 分析模块
│   │   │   │   ├── task/                      # 任务管理模块
│   │   │   │   ├── character/                 # 人物管理模块
│   │   │   │   ├── setting/                   # 设定管理模块
│   │   │   │   └── main/                      # 主页面
│   │   │   └── worker/                        # WorkManager Workers
│   │   ├── res/                               # 资源文件
│   │   └── AndroidManifest.xml
│   ├── build.gradle.kts                       # App 级构建配置
│   └── proguard-rules.pro
├── build.gradle.kts                           # 项目级构建配置
├── settings.gradle.kts
└── gradle.properties
```

---

## 7. 实现路线图

### Phase 1: 基础框架 (4-6 周)

- [ ] 项目初始化（Kotlin + Compose + Hilt + Room）
- [ ] 网络层搭建（Retrofit + sail_server API 对接）
- [ ] 数据库设计（ChapterCache, ReadingProgress）
- [ ] 基础 UI 框架（导航、主题）
- [ ] 作品列表页
- [ ] 章节列表页

### Phase 2: 核心功能 (4-6 周)

- [ ] 阅读器实现（竖向滚动、主题切换）
- [ ] LLM 服务集成（Moonshot/OpenAI/Gemini）
- [ ] 对话式分析界面
- [ ] 后台任务框架（WorkManager）
- [ ] 分析任务创建与监控
- [ ] 任务完成通知

### Phase 3: 数据同步与增强 (3-4 周)

- [ ] 离线阅读支持（章节缓存）
- [ ] 阅读进度同步
- [ ] 人物档案浏览
- [ ] 设定管理浏览
- [ ] 大纲树形展示

### Phase 4: 优化与发布 (2-3 周)

- [ ] 性能优化（列表懒加载、图片缓存）
- [ ] 错误处理与重试机制
- [ ] 用户反馈收集
- [ ] Google Play 发布准备

---

## 8. 技术依赖

### 8.1 核心依赖

```kotlin
// build.gradle.kts
dependencies {
    // AndroidX Core
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    
    // Compose UI
    implementation("androidx.compose.ui:ui:1.6.0")
    implementation("androidx.compose.material3:material3:1.2.0")
    implementation("androidx.navigation:navigation-compose:2.7.6")
    
    // Architecture Components
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.7.0")
    implementation("androidx.room:room-runtime:2.6.1")
    kapt("androidx.room:room-compiler:2.6.1")
    implementation("androidx.room:room-ktx:2.6.1")
    
    // Dependency Injection
    implementation("com.google.dagger:hilt-android:2.50")
    kapt("com.google.dagger:hilt-compiler:2.50")
    implementation("androidx.hilt:hilt-navigation-compose:1.1.0")
    
    // Networking
    implementation("com.squareup.retrofit2:retrofit:2.9.0")
    implementation("com.squareup.retrofit2:converter-gson:2.9.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    
    // Background Work
    implementation("androidx.work:work-runtime-ktx:2.9.0")
    
    // DataStore (Preferences)
    implementation("androidx.datastore:datastore-preferences:1.0.0")
    
    // Firebase (Push Notification)
    implementation("com.google.firebase:firebase-messaging:23.4.0")
    
    // Markdown Rendering
    implementation("io.noties.markwon:core:4.6.2")
    
    // Testing
    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.1.5")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4:1.6.0")
}
```

### 8.2 LLM API 配置

```kotlin
// 配置示例
object LLMConfig {
    const val MOONSHOT_BASE_URL = "https://api.moonshot.cn/v1/"
    const val OPENAI_BASE_URL = "https://api.openai.com/v1/"
    const val GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/"
    
    // 默认模型
    const val DEFAULT_MODEL = "kimi-k2.5"
    const val DEFAULT_PROVIDER = "moonshot"
}
```

---

## 9. 与现有系统集成

### 9.1 后端适配

sail_server 无需重大修改，主要复用现有 `/api/v1/analysis/*` 接口。

### 9.2 前端 Web 端共存

| 场景 | 处理方式 |
|------|----------|
| 阅读进度 | 通过后端 API 同步，两端共享 |
| 分析任务 | Android 可创建任务，Web 端也可查看 |
| 分析结果 | 统一存储于后端，两端均可访问 |
| 离线内容 | Android 本地缓存，Web 依赖在线 |

### 9.3 用户认证

建议实现简单的 API Key 认证：
- 用户在设置中配置后端地址和 API Key
- 后续请求携带 `Authorization: Bearer <api_key>` 头部

---

## 10. 风险评估与应对

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| 团队 Kotlin 学习成本 | 中 | 中 | 提供 Kotlin 培训资源，分阶段迭代 |
| LLM API 密钥安全 | 中 | 高 | 支持用户本地配置，不硬编码密钥 |
| 后台任务被系统杀死 | 高 | 中 | 使用 WorkManager + 通知提示用户 |
| 数据同步冲突 | 中 | 中 | 时间戳策略 + 用户确认机制 |
| 后端 API 变更 | 低 | 高 | 版本化 API，保持向后兼容 |

---

## 11. 附录

### 11.1 参考资源

- [Jetpack Compose 文档](https://developer.android.com/jetpack/compose)
- [Kotlin 协程指南](https://kotlinlang.org/docs/coroutines-guide.html)
- [Room 数据库指南](https://developer.android.com/training/data-storage/room)
- [WorkManager 指南](https://developer.android.com/topic/libraries/architecture/workmanager)

### 11.2 相关文档

- [文本分析系统设计](./text-analysis-system.md)
- [后端 API 文档](../site/doc/) (待完善)
- [LLM 配置指南](../../sail_server/utils/llm/available_providers.py)

---

*文档结束*
