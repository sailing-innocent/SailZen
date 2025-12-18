/**
 * Jest configuration for @saili/unified
 * Extends the base monorepo configuration
 */
import baseConfig from "../../jest.config.base.mjs";

export default {
  ...baseConfig,
  
  // Package-specific display name for parallel test runs
  displayName: "unified",
  
  // Use the package's tsconfig for tests
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: "tsconfig.json",
        useESM: true,
      },
    ],
  },
  
  // Module name mapping for problematic dependencies
  moduleNameMapper: {
    ...baseConfig.moduleNameMapper,
    // Mock rehype-mermaid to avoid mermaid-isomorphic issues
    "^rehype-mermaid$": "<rootDir>/src/__mocks__/rehype-mermaid.ts",
  },
};
