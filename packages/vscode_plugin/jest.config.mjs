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

  },
  // Transform ESM-only packages in node_modules (handle pnpm nested structure)
  // Common ESM-only deps: github-slugger, nanoid, vscode-uri
  // @saili/common-all is symlinked and must be transformed (compiled ESM .js)
  transformIgnorePatterns: [
    "node_modules/(?!.*(github-slugger|nanoid|vscode-uri|@saili/common-all|unified|unist-|mdast-|remark|vfile|micromark|decode-named-character-reference|character-entities|trim-lines|stringify-entities|ccount|markdown-table|longest-streak|escape-string-regexp|is-.*|hast-|property-information|space-separated-tokens|comma-separated-tokens|web-namespaces|zwitch|fault))",
  ],
  transform: {
    "^.+\\.tsx?$": [
      "ts-jest",
      {
        tsconfig: "<rootDir>/tsconfig.test.json",
        useESM: true,
      },
    ],
    "^.+\\.js$": [
      "ts-jest",
      {
        tsconfig: "<rootDir>/tsconfig.test.json",
        useESM: true,
      },
    ],
  },
  // VSCode modules are external; mock them in tests
  modulePathIgnorePatterns: ["/dist/", "/node_modules/"],
};
