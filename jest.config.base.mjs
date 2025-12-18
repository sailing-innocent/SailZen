/**
 * Jest Base Configuration for Monorepo
 * 
 * This is the shared base configuration for all packages in the monorepo.
 * Individual packages should extend this configuration via their own jest.config.mjs.
 * 
 * Usage in package:
 * ```js
 * import baseConfig from '../../jest.config.base.mjs';
 * export default {
 *   ...baseConfig,
 *   // package-specific overrides
 * };
 * ```
 */

export default {
  // ESM preset for TypeScript
  preset: "ts-jest/presets/default-esm",
  
  // Use Node.js environment
  testEnvironment: "node",
  
  // Treat .ts files as ESM
  extensionsToTreatAsEsm: [".ts"],
  
  // ts-jest transformer configuration
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: "tsconfig.json",
        useESM: true,
      },
    ],
  },
  
  // Handle ESM import extensions
  moduleNameMapper: {
    "^(\\.{1,2}/.*)\\.js$": "$1",
  },
  
  // Supported file extensions
  moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node"],
  
  // Test file patterns - supports both __tests__ directories and *.test.ts files
  testMatch: [
    "**/src/**/__tests__/**/*.test.ts",
    "**/src/**/__tests__/**/*.test.tsx",
  ],
  
  // Ignore patterns
  testPathIgnorePatterns: [
    "/node_modules/",
    "/lib/",
    "/dist/",
    "\\.d\\.ts$",
  ],
  
  // Coverage configuration
  collectCoverageFrom: [
    "src/**/*.{ts,tsx}",
    "!src/**/*.d.ts",
    "!src/**/__tests__/**",
    "!src/**/index.ts",  // Entry files usually just re-export
  ],
  
  // Coverage thresholds - start low, increase as coverage improves
  coverageThreshold: {
    global: {
      branches: 10,
      functions: 10,
      lines: 10,
      statements: 10,
    },
  },
  
  // Coverage report formats
  coverageReporters: ["text", "lcov", "html"],
  
  // Coverage output directory
  coverageDirectory: "coverage",
  
  // Clear mocks between tests
  clearMocks: true,
  
  // Restore mocks after each test
  restoreMocks: true,
  
  // Verbose output for debugging
  verbose: true,
};
