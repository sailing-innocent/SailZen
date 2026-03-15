## ADDED Requirements

### Requirement: Expo project initialization
The mobile app SHALL be initialized as an Expo project with TypeScript support.

#### Scenario: Project setup
- **WHEN** the developer runs `npx create-expo-app mobile --template blank-typescript`
- **THEN** a working Expo project is created in `mobile/` directory
- **AND** the project can be started with `npx expo start`

### Requirement: Navigation structure
The app SHALL use Expo Router for file-system based navigation with tab layout.

#### Scenario: Tab navigation
- **WHEN** the user opens the app
- **THEN** they see a bottom tab bar with tabs: 体重, 运动, 目标
- **AND** each tab navigates to the corresponding screen

### Requirement: Theme system
The app SHALL use React Native Paper with a consistent theme matching the brand colors.

#### Scenario: Theme application
- **WHEN** any screen is rendered
- **THEN** components use the defined color scheme
- **AND** light/dark mode is supported (optional for phase 1)

### Requirement: Android platform support
The app SHALL target Android platform only in phase 1.

#### Scenario: Android build
- **WHEN** the developer runs `eas build --platform android`
- **THEN** an APK/AAB file is generated
- **AND** the app installs and runs on Android devices

