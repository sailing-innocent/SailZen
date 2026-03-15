## Why

当前 SailZen 的 Web 前端 UI 精细度不足，在移动端体验有限。为了提供更流畅的移动端体验，同时验证 Web 端与移动端同步开发的可行性，我们需要引入原生 Android 应用作为新的前端入口。

## What Changes

- **新增**: 使用 Expo + React Native 构建的 Android 移动应用
- **新增**: 独立的移动端代码库 `mobile/`，与现有 Web 端解耦
- **新增**: 移动端专用的 API 客户端和数据同步机制
- **新增**: 健康模块移动端完整功能（体重记录、运动记录、体重目标规划）
- **新增**: 离线数据存储与同步机制
- **验证**: Web 端与移动端并行开发的工作流

## Capabilities

### New Capabilities
- `mobile-health-app`: 移动端健康应用主体框架，包含 Expo 项目配置、导航、主题系统
- `mobile-weight-tracking`: 移动端体重记录功能，支持快速记录、历史查看、趋势图表
- `mobile-exercise-tracking`: 移动端运动记录功能，支持运动类型、时长、热量记录
- `mobile-weight-planning`: 移动端体重目标规划功能，支持设置目标体重、查看进度
- `mobile-offline-sync`: 移动端离线数据存储与后端同步机制
- `mobile-api-client`: 移动端专用 API 客户端，封装后端通信

### Modified Capabilities
- （无修改，后端 API 保持不变）

## Impact

- **架构**: 新增 `mobile/` 目录作为独立子项目，不破坏现有结构
- **依赖**: 新增 React Native、Expo、AsyncStorage、React Navigation 等依赖
- **API**: 复用现有 `/api/v1/health/*` 端点，无需后端修改
- **开发流程**: 需要同时维护 Web 端和移动端，验证并行开发效率
- **部署**: 新增 Android APK/AAB 构建流程

