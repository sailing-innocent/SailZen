/**
 * Jest configuration for @saili/api-server
 * Extends the base monorepo configuration
 */
import baseConfig from "../../jest.config.base.mjs";

export default {
  ...baseConfig,
  displayName: "api-server",
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
  // Transform ESM-only packages in node_modules (handle pnpm nested structure)
  // @saili/* packages are symlinked and must be transformed (compiled ESM .js)
  transformIgnorePatterns: [
    "node_modules/(?!.*(github-slugger|nanoid|vscode-uri|@saili/common-all|@saili/common-server|@saili/unified|unified|unist-|mdast-|remark|vfile|micromark|decode-named-character-reference|character-entities|trim-lines|stringify-entities|ccount|markdown-table|longest-streak|escape-string-regexp|is-.*|hast-|property-information|space-separated-tokens|comma-separated-tokens|web-namespaces|zwitch|fault))",
  ],
  moduleNameMapper: {
    "^(\\.{1,2}/.*)\\.js$": "$1",
  },
};
