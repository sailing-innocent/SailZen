## 0. Environment Compatibility (重要修复)

- [x] 0.1 修复 Expo SDK 50 与 Node.js 20+ 的兼容性问题
  - 问题: Node.js 20+ 引入的 `node:sea` 模块在 Windows 上导致 Metro 构建失败
  - 解决方案: 升级 Expo SDK 从 50.0.0 到 54.0.33 (适配 Expo Go 54)
  - 相关更新:
    - expo: ~50.0.0 → ~54.0.33
    - expo-status-bar: ~1.11.0 → ~3.0.9
    - expo-sqlite: ~13.3.0 → ~16.0.10
    - expo-router: ~3.4.0 → ~4.0.22
    - expo-notifications: ~0.27.0 → ~0.32.16
    - expo-constants: ~15.4.0 → ~18.0.13
    - react: 18.2.0 → 19.1.0
    - react-native: 0.73.0 → 0.81.5
    - react-native-screens: ~3.29.0 → ~4.16.0
    - react-native-gesture-handler: ~2.14.0 → ~2.28.0
    - react-native-safe-area-context: 4.8.2 → 5.6.0
    - react-native-paper: ^5.12.0 → ^5.13.0
    - @react-native-community/netinfo: 11.1.0 → 11.4.1
    - @types/react: ~18.2.45 → ~19.1.0
    - @react-navigation/native: ^6.1.9 → ^7.1.0
    - @react-navigation/bottom-tabs: ^6.5.11 → ^7.3.0
    - zustand: ^4.5.0 → ^5.0.0
    - axios: ^1.6.0 → ^1.8.0
    - drizzle-orm: ^0.29.0 → ^0.41.0
    - drizzle-kit: ^0.20.0 → ^0.31.0
    - date-fns: ^3.0.0 → ^4.0.0
  - 新增依赖:
    - @expo/metro-runtime: ~4.0.1 (Expo SDK 54 必需)
  - 配置文件更新:
    - 移除 babel.config.js 中的 `expo-router/babel` 插件（新版本的 router 不再需要）
    - 简化 metro.config.js
    - 从 app.json 中移除 `extra.router.origin`
    - **重要**: 修改 package.json 的 `main` 字段从 `expo/AppEntry.js` 改为 `expo-router/entry` (Expo Router 4.x 要求)
  - 新增 assets 图标文件:
    - icon.png (1024x1024)
    - splash.png (2048x2048)
    - adaptive-icon.png (1024x1024)
    - favicon.png (256x256)
  - Expo Go 兼容性: ✅ SDK 54 与 Expo Go 54 完全兼容

## 1. Project Setup

- [x] 1.1 Initialize Expo project with TypeScript template in `packages/mobile/` directory
- [x] 1.2 Configure ESLint and Prettier for mobile project
- [x] 1.3 Install React Native Paper and configure theme
- [x] 1.4 Set up Expo Router with tab navigation structure
- [x] 1.5 Create environment configuration files (.env.development, .env.production)
- [x] 1.6 Add necessary dependencies (Zustand, Axios, expo-sqlite, drizzle-orm)
- [x] 1.7 Configure Drizzle ORM with SQLite for local storage
- [x] 1.8 Create TypeScript type definitions for all data models

## 2. Database Layer

- [x] 2.1 Create Drizzle schema for weight records table
- [x] 2.2 Create Drizzle schema for exercise records table
- [x] 2.3 Create Drizzle schema for weight plans table
- [x] 2.4 Create Drizzle schema for sync metadata table
- [ ] 2.5 Implement database initialization on app launch
- [ ] 2.6 Create database utility hooks (useDatabase, useMigrations)
- [ ] 2.7 Add database debugging tools for development

## 3. API Client

- [x] 3.1 Create base API client with Axios instance
- [x] 3.2 Implement request/response interceptors for logging
- [x] 3.3 Implement weight API endpoints (get list, create, stats, analysis)
- [x] 3.4 Implement exercise API endpoints (get list, create, update, delete)
- [x] 3.5 Implement weight plan API endpoints (get, create, progress)
- [x] 3.6 Add error handling and retry logic for network failures
- [x] 3.7 Create API types matching backend DTOs

## 4. State Management

- [x] 4.1 Create Zustand store for weight records
- [x] 4.2 Create Zustand store for exercise records
- [x] 4.3 Create Zustand store for weight plans
- [x] 4.4 Create Zustand store for sync status
- [x] 4.5 Implement persistence middleware for stores
- [ ] 4.6 Create custom hooks for data operations (useWeights, useExercises, useWeightPlan)

## 5. Weight Tracking Feature

- [ ] 5.1 Create weight input form component
- [ ] 5.2 Implement quick weight recording on home screen
- [ ] 5.3 Create weight history list with pagination
- [ ] 5.4 Implement weight statistics display (avg, min, max)
- [ ] 5.5 Integrate react-native-gifted-charts for weight trend chart
- [ ] 5.6 Implement time range selector (7d, 30d, 90d, all)
- [ ] 5.7 Add edit and delete functionality for weight records
- [ ] 5.8 Create weight detail view screen

## 6. Exercise Tracking Feature

- [ ] 6.1 Create exercise type selector component
- [ ] 6.2 Implement duration input with quick-select options
- [ ] 6.3 Add calorie calculation based on MET values
- [ ] 6.4 Create exercise history list with date grouping
- [ ] 6.5 Implement exercise statistics cards
- [ ] 6.6 Create exercise record form with validation
- [ ] 6.7 Implement edit and delete for exercise records
- [ ] 6.8 Add exercise detail view screen

## 7. Weight Planning Feature

- [ ] 7.1 Create weight goal creation form
- [ ] 7.2 Implement form validation for goal inputs
- [ ] 7.3 Create current goal display with progress bar
- [ ] 7.4 Calculate and display progress percentage
- [ ] 7.5 Implement goal status indicators (正常, 落后, 超前)
- [ ] 7.6 Create goal progress chart with expected vs actual
- [ ] 7.7 Add goal history list view
- [ ] 7.8 Implement goal editing and deletion

## 8. Offline Sync Feature

- [ ] 8.1 Implement network status detection hook
- [x] 8.2 Create sync service for batch operations
- [x] 8.3 Implement pending changes tracking
- [ ] 8.4 Create sync button with pending count badge
- [x] 8.5 Implement upload of pending records to server
- [ ] 8.6 Implement download of server records
- [ ] 8.7 Add conflict resolution (last-write-wins)
- [ ] 8.8 Implement auto-sync on connection restore
- [ ] 8.9 Create sync error handling and retry logic
- [ ] 8.10 Add last sync time display and stale data warning

## 9. Push Notifications

- [ ] 9.1 Configure expo-notifications and request permissions
- [ ] 9.2 Create notification service with scheduling API
- [ ] 9.3 Implement daily weight reminder notification (configurable time)
- [ ] 9.4 Implement weekly exercise progress notification
- [ ] 9.5 Create weight goal milestone celebration notification
- [ ] 9.6 Add offline data sync reminder notification
- [ ] 9.7 Create notification settings screen
- [ ] 9.8 Implement notification permission handling and guidance
- [ ] 9.9 Test notification delivery in background and foreground
- [ ] 9.10 Add notification analytics (optional)

## 10. UI/UX Polish

- [x] 10.1 Implement consistent color scheme with theme provider
- [ ] 10.2 Add loading states and skeleton screens
- [ ] 10.3 Implement empty states for lists
- [ ] 10.4 Add pull-to-refresh functionality
- [ ] 10.5 Create error boundary for crash handling
- [ ] 10.6 Implement offline mode indicator
- [ ] 10.7 Add haptic feedback for actions
- [ ] 10.8 Optimize list performance with FlatList

## 11. Testing & Build

- [ ] 11.1 Configure EAS Build for Android
- [ ] 11.2 Create development build for testing
- [ ] 11.3 Test weight tracking flow end-to-end
- [ ] 11.4 Test exercise tracking flow end-to-end
- [ ] 11.5 Test weight planning flow end-to-end
- [ ] 11.6 Test offline sync scenarios
- [ ] 11.7 Test push notification delivery
- [ ] 11.8 Perform UI testing on different screen sizes
- [ ] 11.9 Build production APK/AAB
- [ ] 11.10 Write basic documentation (README.md for mobile/)
- [ ] 11.11 Create CHANGELOG.md for mobile releases

## 12. Verification with Web Team

- [ ] 12.1 Document API usage and any inconsistencies found
- [ ] 12.2 Share mobile UX patterns with Web team
- [ ] 12.3 Verify data compatibility between mobile and web
- [ ] 12.4 Test parallel development workflow
- [ ] 12.5 Document lessons learned for future mobile features
