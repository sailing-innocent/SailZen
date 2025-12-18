import * as vscode from "vscode";
import { Logger } from "./logger";
import { DWorkspace } from "./workspacev2";
import { activate as _activate, deactivate as _deactivate } from "./_extension";

// Workaround for remark-variables@1.4.9 bug: undeclared variables
// The library uses 'actual' and 'val' without declaring them, causing ReferenceError in strict mode
// See: https://github.com/... (library issue)
(globalThis as any).actual = undefined;
(globalThis as any).val = undefined;

export function activate(context: vscode.ExtensionContext) {
  Logger.configure(context, "debug");
  _activate(context);
  return {
    DWorkspace,
    Logger,
  };
}

export function deactivate() {
  _deactivate();
}
