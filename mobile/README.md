# SailZen Mobile

SailZen Mobile 是 SailZen 项目的原生 Android 移动端应用，使用 Expo + React Native + TypeScript 构建。

## 技术栈

- **框架**: Expo SDK 50 + React Native 0.73
- **语言**: TypeScript
- **导航**: Expo Router (文件系统路由)
- **UI**: React Native Paper (Material Design 3)
- **状态管理**: Zustand
- **本地存储**: SQLite + Drizzle ORM
- **HTTP 客户端**: Axios
- **图表**: react-native-gifted-charts

## 项目结构

```
mobile/
├── src/
│   ├── app/               # Expo Router 页面
│   │   ├── (tabs)/        # Tab 导航
│   │   │   ├── index.tsx  # 体重记录
│   │   │   ├── exercise.tsx # 运动记录
│   │   │   ├── plan.tsx   # 目标规划
│   │   │   └── _layout.tsx
│   │   ├── _layout.tsx    # 根布局
│   │   └── theme.ts       # 主题配置
│   ├── components/        # 共享组件
│   ├── hooks/             # 自定义 Hooks
│   ├── stores/            # Zustand 状态管理
│   │   ├── weightStore.ts
│   │   ├── exerciseStore.ts
│   │   ├── weightPlanStore.ts
│   │   └── syncStore.ts
│   ├── api/               # API 客户端
│   │   └── client.ts
│   ├── db/                # 数据库
│   │   ├── index.ts
│   │   └── schema.ts
│   └── types/             # TypeScript 类型
│       └── index.ts
├── assets/                # 图片资源
├── app.json              # Expo 配置
├── package.json          # 依赖
└── README.md
```

## 开发环境配置

### 前提条件

- Node.js >= 18
- pnpm (推荐)
- Android Studio (用于模拟器)
- Expo CLI: `npm install -g expo-cli`

### 安装依赖

```bash
cd mobile
pnpm install
```

### 环境变量

创建 `.env.local` 文件：

```
API_BASE_URL=http://localhost:8000/api/v1
API_TIMEOUT=10000
```

### 启动开发服务器

```bash
# 使用 Expo Go 应用
npx expo start

# 或创建开发构建
npx expo run:android
```

## 功能模块

### 1. 体重记录
- 快速体重录入
- 体重历史列表
- 趋势图表
- 统计分析

### 2. 运动记录
- 运动类型选择（跑步、游泳、骑行、健身、瑜伽、其他）
- 时长记录
- 卡路里估算（基于 MET 值）
- 运动历史

### 3. 体重目标
- 目标设定
- 进度追踪
- 状态指示（正常、落后、超前）

### 4. 数据同步
- 离线优先策略
- 手动同步
- 自动同步（网络恢复时）
- 冲突解决（服务器优先）

## 数据库模型

### WeightRecord
- value: 体重值 (kg)
- recordTime: 记录时间
- syncStatus: 同步状态 (synced/pending/error)
- serverId: 服务器 ID

### ExerciseRecord
- type: 运动类型
- duration: 时长（分钟）
- calories: 卡路里
- recordTime: 记录时间
- syncStatus: 同步状态

### WeightPlan
- targetWeight: 目标体重
- targetDate: 目标日期
- startWeight: 起始体重
- startDate: 起始日期
- isActive: 是否激活
- syncStatus: 同步状态

## API 接口

后端 API 地址: `/api/v1/health`

### 体重相关
- GET /health/weight - 获取体重列表
- POST /health/weight - 创建体重记录
- GET /health/weight/avg - 获取统计数据
- GET /health/weight/analysis - 趋势分析

### 运动相关
- GET /health/exercise - 获取运动列表
- POST /health/exercise - 创建运动记录
- PUT /health/exercise/:id - 更新运动记录
- DELETE /health/exercise/:id - 删除运动记录

### 目标相关
- GET /health/weight/plan - 获取当前目标
- POST /health/weight/plan - 创建目标
- GET /health/weight/plan/progress - 获取进度

## 构建与发布

### 开发构建

```bash
eas build --profile development --platform android
```

### 预览构建

```bash
eas build --profile preview --platform android
```

### 生产构建

```bash
eas build --profile production --platform android
```

## 与 Web 端同步开发

移动端与 Web 端（packages/site）共享同一后端 API，实现了真正的并行开发：

1. **后端优先**: API 定义先行，多端消费
2. **独立迭代**: 移动端和 Web 端独立发布版本
3. **数据兼容**: 两端数据模型保持一致
4. **UI 差异化**: 移动端针对触摸优化，Web 端针对桌面优化

## 已知问题

- iOS 平台暂未支持（Phase 1 仅限 Android）
- 实时同步功能暂未实现（使用手动同步）

## 待办事项

- [ ] 完善 UI 组件
- [ ] 添加图表展示
- [ ] 实现推送通知
- [ ] 添加数据导入/导出
- [ ] iOS 平台支持

## 贡献指南

1. Fork 项目
2. 创建特性分支: `git checkout -b feature/new-feature`
3. 提交更改: `git commit -am 'Add new feature'`
4. 推送到分支: `git push origin feature/new-feature`
5. 提交 Pull Request

## License

MIT License - 详见项目根目录 LICENSE 文件
