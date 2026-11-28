import {
  SailEditorViewKey,
  getWebEditorViewEntry,
} from "@saili/common-all";
import * as vscode from "vscode";
import { SAIL_COMMANDS } from "../constants";
import { ExtensionProvider } from "../ExtensionProvider";
import { WebViewUtils } from "../views/utils";
import { BasicCommand } from "./base";

type CommandOpts = {};

type CommandOutput = void;

export class ConfigureWithUICommand extends BasicCommand<
  CommandOpts,
  CommandOutput
> {
  public static requireActiveWorkspace: boolean = true;
  private _panel;
  key = SAIL_COMMANDS.CONFIGURE_UI.key;
  constructor(panel: vscode.WebviewPanel) {
    super();
    this._panel = panel;
  }

  async gatherInputs(): Promise<any> {
    return {};
  }
  async execute() {
    const { bundleName: name } = getWebEditorViewEntry(
      SailEditorViewKey.CONFIGURE
    );
    const ext = ExtensionProvider.getExtension();
    const port = ext.port!;
    const engine = ext.getEngine();
    const { wsRoot } = engine;
    const webViewAssets = WebViewUtils.getJsAndCss();
    const html = await WebViewUtils.getWebviewContent({
      ...webViewAssets,
      name,
      port,
      wsRoot,
      panel: this._panel,
    });

    this._panel.webview.html = html;
  }
}
