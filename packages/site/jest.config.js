/** @type {import('ts-jest').JestConfigWithTsJest} **/
export default {
  testEnvironment: "node",
  setupFiles: ['<rootDir>/src/jest-setup.ts'],
  transform: {
    "^.+.tsx?$": ["ts-jest",{}],
  },
  moduleNameMapper: {
    "^@lib/(.*)$": "<rootDir>/src/lib/$1",
    "^@components/(.*)$": "<rootDir>/src/components/$1", 
    "^@pages/(.*)$": "<rootDir>/src/pages/$1",
    "^@shaders/(.*)$": "<rootDir>/src/shaders/$1",
    "^@/(.*)$": "<rootDir>/src/$1",
  },
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  testMatch: ['**/*.test.ts', '**/*.test.tsx'],
};
