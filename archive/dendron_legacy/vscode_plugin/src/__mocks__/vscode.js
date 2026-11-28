/**
 * @file vscode.js
 * @brief Mock for the vscode module in Jest tests
 */

class EventEmitter {
  constructor() {
    this._listeners = [];
    this.event = (listener) => {
      this._listeners.push(listener);
      return {
        dispose: () => {
          const idx = this._listeners.indexOf(listener);
          if (idx >= 0) {
            this._listeners.splice(idx, 1);
          }
        },
      };
    };
  }
  fire(data) {
    for (const listener of [...this._listeners]) {
      listener(data);
    }
  }
  dispose() {
    this._listeners = [];
  }
}

class FileSystemError extends Error {
  static FileNotFound(message) {
    return new FileSystemError(message || "File not found");
  }
  static FileExists(message) {
    return new FileSystemError(message || "File exists");
  }
}

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
  EventEmitter,
  FileSystemError,
};
