module.exports = {
  preset: "ts-jest",
  testEnvironment: "node",
  roots: ["<rootDir>/tests"],
  testMatch: ["**/*.test.ts"],
  moduleFileExtensions: ["ts", "js", "json"],
  transform: {
    "^.+\\.tsx?$": ["ts-jest", { tsconfig: { module: "CommonJS", moduleResolution: "node10", ignoreDeprecations: "6.0" } }],
  },
};
