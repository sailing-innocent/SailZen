import baseConfig from "../../jest.config.base.mjs";

export default {
  ...baseConfig,
  displayName: "vscode-plugin",
  testMatch: [
    "**/src/**/__tests__/**/*.test.ts",
    "**/src/**/__tests__/**/*.test.tsx",
  ],
  moduleNameMapper: {
    "^(\\.{1,2}/.*)\\.js$": "$1",
    "^vscode$": "<rootDir>/src/__mocks__/vscode.js",
    "^@saili/common-all$": "<rootDir>/../common-all/src/index.ts",
  },
  // Transform ESM-only packages in node_modules (handle pnpm nested structure)
  // Common ESM-only deps: github-slugger, nanoid, vscode-uri
  transformIgnorePatterns: [
    "node_modules/(?!.*(github-slugger|nanoid|vscode-uri))",
  ],
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: "tsconfig.json",
        useESM: true,
      },
    ],
    "^.+\\.js$": [
      "ts-jest",
      {
        tsconfig: "tsconfig.json",
        useESM: true,
      },
    ],
  },
  // VSCode modules are external; mock them in tests
  modulePathIgnorePatterns: ["/dist/", "/node_modules/"],
};
