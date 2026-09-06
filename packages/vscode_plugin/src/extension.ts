import * as vscode from "vscode";
import { Logger } from "./logger";
import { activate as _activate, deactivate as _deactivate } from "./_extension";

export function activate(context: vscode.ExtensionContext) {
  Logger.configure(context, "debug");
  _activate(context);
  return {
    Logger,
  };
}

export function deactivate() {
  _deactivate();
}
