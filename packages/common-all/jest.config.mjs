/**
 * Jest configuration for ESM module
 * Using .mjs extension to support ESM
 */
export default {
  preset: "ts-jest/presets/default-esm",
  testEnvironment: "node",
  extensionsToTreatAsEsm: [".ts"],
  // 使用新的 ts-jest 配置格式
  transform: {
    "^.+\\.ts$": [
      "ts-jest",
      {
        tsconfig: "tsconfig.json",
        useESM: true,
      },
    ],
  },
  moduleNameMapper: {
    // 处理文件扩展名映射
    "^(\\.{1,2}/.*)\\.js$": "$1",
  },
  moduleFileExtensions: ["ts", "js", "json", "node"],
  // 排除 lib 目录（编译输出）和类型定义文件
  testMatch: [
    "**/src/**/*.test.ts",
    "**/src/**/__tests__/**/*.ts",
  ],
  // 排除不需要测试的文件和目录
  testPathIgnorePatterns: [
    "/node_modules/",
    "/lib/",
    "\\.d\\.ts$",
  ],
  // 覆盖率配置
  collectCoverageFrom: [
    "src/**/*.{ts,tsx}",
    "!src/**/*.d.ts",
    "!src/**/__tests__/**",
    "!src/**/*.test.ts",
    "!src/index.ts", // 入口文件通常不需要测试
  ],
  // 覆盖率阈值（可根据项目需要调整）
  // 当前设置为较低阈值，因为测试覆盖率还在逐步提升中
  // 建议随着测试的增加逐步提高这些阈值
  coverageThreshold: {
    global: {
      branches: 10,
      functions: 10,
      lines: 10,
      statements: 10,
    },
  },
  // 覆盖率报告格式
  coverageReporters: ["text", "lcov", "html"],
};
