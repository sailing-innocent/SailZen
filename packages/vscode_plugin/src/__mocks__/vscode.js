/**
 * @file vscode.js
 * @brief Mock for the vscode module in Jest tests
 */

module.exports = {
  workspace: {
    fs: {
      readFile: jest.fn(),
      writeFile: jest.fn(),
      stat: jest.fn(),
      readDirectory: jest.fn(),
    },
  },
  Uri: {
    file: (path) => ({ fsPath: path, path, toString: () => path }),
    parse: (uri) => ({ fsPath: uri, path: uri, toString: () => uri }),
  },
};
