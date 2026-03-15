## 1. Project Setup

- [ ] 1.1 Initialize Expo project with TypeScript template in `mobile/` directory
- [ ] 1.2 Configure ESLint and Prettier for mobile project
- [ ] 1.3 Install React Native Paper and configure theme
- [ ] 1.4 Set up Expo Router with tab navigation structure
- [ ] 1.5 Create environment configuration files (.env.development, .env.production)
- [ ] 1.6 Add necessary dependencies (Zustand, Axios, expo-sqlite, drizzle-orm)
- [ ] 1.7 Configure Drizzle ORM with SQLite for local storage
- [ ] 1.8 Create TypeScript type definitions for all data models

## 2. Database Layer

- [ ] 2.1 Create Drizzle schema for weight records table
- [ ] 2.2 Create Drizzle schema for exercise records table
- [ ] 2.3 Create Drizzle schema for weight plans table
- [ ] 2.4 Create Drizzle schema for sync metadata table
- [ ] 2.5 Implement database initialization on app launch
- [ ] 2.6 Create database utility hooks (useDatabase, useMigrations)
- [ ] 2.7 Add database debugging tools for development

## 3. API Client

- [ ] 3.1 Create base API client with Axios instance
- [ ] 3.2 Implement request/response interceptors for logging
- [ ] 3.3 Implement weight API endpoints (get list, create, stats, analysis)
- [ ] 3.4 Implement exercise API endpoints (get list, create, update, delete)
- [ ] 3.5 Implement weight plan API endpoints (get, create, progress)
- [ ] 3.6 Add error handling and retry logic for network failures
- [ ] 3.7 Create API types matching backend DTOs

## 4. State Management

- [ ] 4.1 Create Zustand store for weight records
- [ ] 4.2 Create Zustand store for exercise records
- [ ] 4.3 Create Zustand store for weight plans
- [ ] 4.4 Create Zustand store for sync status
- [ ] 4.5 Implement persistence middleware for stores
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
- [ ] 8.2 Create sync service for batch operations
- [ ] 8.3 Implement pending changes tracking
- [ ] 8.4 Create sync button with pending count badge
- [ ] 8.5 Implement upload of pending records to server
- [ ] 8.6 Implement download of server records
- [ ] 8.7 Add conflict resolution (last-write-wins)
- [ ] 8.8 Implement auto-sync on connection restore
- [ ] 8.9 Create sync error handling and retry logic
- [ ] 8.10 Add last sync time display and stale data warning

## 9. UI/UX Polish

- [ ] 9.1 Implement consistent color scheme with theme provider
- [ ] 9.2 Add loading states and skeleton screens
- [ ] 9.3 Implement empty states for lists
- [ ] 9.4 Add pull-to-refresh functionality
- [ ] 9.5 Create error boundary for crash handling
- [ ] 9.6 Implement offline mode indicator
- [ ] 9.7 Add haptic feedback for actions
- [ ] 9.8 Optimize list performance with FlatList

## 10. Testing & Build

- [ ] 10.1 Configure EAS Build for Android
- [ ] 10.2 Create development build for testing
- [ ] 10.3 Test weight tracking flow end-to-end
- [ ] 10.4 Test exercise tracking flow end-to-end
- [ ] 10.5 Test weight planning flow end-to-end
- [ ] 10.6 Test offline sync scenarios
- [ ] 10.7 Perform UI testing on different screen sizes
- [ ] 10.8 Build production APK/AAB
- [ ] 10.9 Write basic documentation (README.md for mobile/)
- [ ] 10.10 Create CHANGELOG.md for mobile releases

## 11. Verification with Web Team

- [ ] 11.1 Document API usage and any inconsistencies found
- [ ] 11.2 Share mobile UX patterns with Web team
- [ ] 11.3 Verify data compatibility between mobile and web
- [ ] 11.4 Test parallel development workflow
- [ ] 11.5 Document lessons learned for future mobile features
