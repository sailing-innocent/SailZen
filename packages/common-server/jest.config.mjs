/**
 * Jest configuration for @saili/common-server
 * Extends the base monorepo configuration
 */
import baseConfig from "../../jest.config.base.mjs";

export default {
  ...baseConfig,
  
  // Package-specific display name for parallel test runs
  displayName: "common-server",
  
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
};
