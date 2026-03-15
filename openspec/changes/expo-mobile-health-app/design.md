## Context

SailZen 是一个基于 VSCode 扩展的个人知识管理工具，由 TypeScript/JavaScript monorepo（前端/扩展）和 Python 后端（Litestar + PostgreSQL）组成。当前 Web 前端使用 React 19 + Tailwind CSS 4，在移动端的精细度不足。

健康模块后端已实现体重记录、运动记录、体重目标规划等 API，Web 端尚未完整对接。团队希望通过引入 Expo + React Native 构建原生 Android 应用，提供更佳的移动端体验，并验证 Web 端与移动端同步开发的可行性。

## Goals / Non-Goals

**Goals:**
- 使用 Expo + React Native 构建独立的 Android 移动应用
- 移动端仅关注健康模块（体重、运动、体重目标）
- 实现离线数据存储与后端同步
- 验证 Web 端与移动端并行开发的工作流程
- 移动端与后端 API 直接通信，不依赖 Web 端代码

**Non-Goals:**
- iOS 平台支持（第一阶段仅限 Android）
- 其他功能模块（财务、项目、文本等）
- 与 Web 端共享 UI 组件或业务逻辑
- 后端架构修改
- 实时数据同步（第一阶段使用手动同步）

## Decisions

### 1. 使用 Expo 而非纯 React Native CLI
**Decision**: 使用 Expo SDK 构建项目

**Rationale**:
- Expo 提供更简单的开发体验和热更新能力
- 无需配置原生 Android 工具链（Android Studio、Gradle 等）
- EAS Build 支持云构建 Android APK/AAB
- 内置 Expo Router 提供文件系统导航
- 适合快速原型验证和小团队开发

**Alternatives Considered**:
- React Native CLI: 更灵活但需要原生开发经验，构建配置复杂
- Flutter: 学习成本较高，与现有 React 技术栈不一致

### 2. 移动端作为独立项目目录
**Decision**: 在 `mobile/` 目录下创建完全独立的 Expo 项目

**Rationale**:
- 与现有 `packages/site` Web 端解耦，避免构建冲突
- 移动端可以独立发布版本，不受 Web 端限制
- 清晰的项目边界，便于团队分工
- Expo 项目结构（`app.json`、`eas.json` 等）与现有 monorepo 不兼容

**Directory Structure**:
```
mobile/
├── App.tsx                 # 应用入口
├── app.json               # Expo 配置
├── eas.json               # EAS Build 配置
├── package.json           # 独立依赖
├── src/
│   ├── app/               # Expo Router 页面
│   │   ├── (tabs)/        # Tab 导航
│   │   │   ├── index.tsx  # 首页（体重）
│   │   │   ├── weight.tsx # 体重详情
│   │   │   ├── exercise.tsx # 运动记录
│   │   │   └── plan.tsx   # 目标规划
│   │   └── _layout.tsx    # 根布局
│   ├── components/        # 共享组件
│   ├── hooks/             # 自定义 Hooks
│   ├── stores/            # Zustand 状态管理
│   ├── api/               # API 客户端
│   ├── db/                # 本地存储（SQLite）
│   └── types/             # TypeScript 类型
└── assets/                # 图片、字体
```

### 3. 离线优先的数据策略
**Decision**: 使用 SQLite 本地存储 + 手动同步机制

**Rationale**:
- 移动端可能处于弱网环境，离线记录是刚需
- 避免实时同步带来的复杂性和冲突处理
- 用户可以控制何时同步数据，节省流量
- 与后端保持最终一致性即可

**Sync Strategy**:
- 本地 SQLite 作为主数据源
- 新增/修改操作先写本地，标记 `sync_status: 'pending'`
- 用户主动触发同步或定时检查
- 同步时批量上传 pending 记录，下载服务器新数据
- 冲突解决：服务器时间戳优先（last-write-wins）

### 4. 技术栈选择

**UI Framework**: React Native Paper
- 提供 Material Design 3 组件
- 良好的 TypeScript 支持
- 主题系统完善

**State Management**: Zustand
- 轻量级，与 Web 端保持一致
- 支持持久化（中间件）
- 无需 Provider 包裹

**本地存储**: expo-sqlite + Drizzle ORM
- SQLite 是 React Native 标准本地存储
- Drizzle 提供类型安全的 SQL 查询
- 支持迁移和关系查询

**HTTP Client**: Axios
- 与 Web 端保持一致
- 支持拦截器和错误处理
- 请求取消和超时控制

**图表**: react-native-gifted-charts
- 专为 React Native 设计的图表库
- 支持折线图、柱状图
- 良好的性能和手势支持

### 5. API 通信架构
**Decision**: 直接复用现有后端 API，移动端独立实现 API 客户端

**Rationale**:
- 后端 `/api/v1/health/*` 端点已稳定，无需修改
- 移动端可以直接调用 REST API
- 避免通过 Web 端代理，减少耦合

**API Client Structure**:
```typescript
// src/api/client.ts
export class ApiClient {
  async getWeightList(params: WeightListParams): Promise<WeightRecord[]>;
  async createWeight(data: WeightCreateData): Promise<WeightRecord>;
  async getExerciseList(params: ExerciseListParams): Promise<ExerciseRecord[]>;
  async createExercise(data: ExerciseCreateData): Promise<ExerciseRecord>;
  async getWeightPlan(): Promise<WeightPlan | null>;
  async createWeightPlan(data: WeightPlanCreateData): Promise<WeightPlan>;
}
```

### 6. 与 Web 端并行开发策略
**Decision**: 移动端独立迭代，通过 API 契约与 Web 端协作

**Rationale**:
- Web 端和移动端使用相同后端 API，天然解耦
- 移动端可以先实现功能，Web 端后续跟进
- 验证"后端优先，多端消费"的架构可行性

**Workflow**:
1. 后端 API 保持稳定（健康模块已实现）
2. 移动端独立开发和测试（使用本地 SQLite）
3. Web 端可选择性地复用移动端验证过的 UX
4. 两端通过 API 版本和文档保持一致

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Expo 构建依赖 EAS 云服务 | 构建需要网络，可能有排队时间 | 配置本地 EAS 代理，或接受云构建的延迟 |
| 离线同步冲突处理复杂 | 数据不一致 | 第一阶段简化冲突策略（服务器优先），后续考虑合并逻辑 |
| 移动端与 Web 端 UI 不一致 | 用户体验割裂 | 建立设计规范，使用相同的颜色、字体、间距变量 |
| SQLite 与后端数据模型差异 | 同步映射复杂 | 保持本地模型与 DTO 一致，使用 Drizzle 迁移管理 |
| 维护两套前端代码库 | 工作量增加 | 聚焦健康模块，其他功能暂缓，验证可行性后再扩展 |

## Migration Plan

### 阶段一：项目搭建（Week 1）
1. 初始化 Expo 项目
2. 配置 TypeScript、ESLint、Prettier
3. 集成 React Native Paper、Zustand、Drizzle
4. 搭建导航结构和主题系统

### 阶段二：本地功能（Week 2-3）
1. 实现 SQLite 数据库模型（体重、运动、目标）
2. 实现记录增删改查（纯本地）
3. 实现图表展示
4. 本地测试和优化

### 阶段三：后端集成（Week 4）
1. 实现 API 客户端
2. 实现同步机制
3. 联调测试
4. 构建测试 APK

### 阶段四：验证与迭代（Week 5）
1. 与 Web 端并行测试
2. 收集反馈，优化体验
3. 完善文档

### Rollback Strategy
- 移动端是新增项目，不影响现有 Web 端
- 如验证失败，可废弃 `mobile/` 目录，不影响主项目

## Open Questions

1. **认证机制**: 当前后端是否需要认证？移动端如何实现登录？
2. **服务器地址**: 移动端如何配置后端 API 地址（开发/生产环境）？
3. **数据保留策略**: 本地 SQLite 数据是否需要清理策略？
4. **图表精度**: 移动端图表是否需要与 Web 端完全一致？
5. **推送通知**: 是否需要提醒用户记录体重、运动？

