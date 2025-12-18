import vscode from "vscode";


export type DWorkspaceInitOpts = {
  onReady: ({}: { ws: DWorkspace }) => Promise<void>; // eslint-disable-line  no-empty-pattern
  numRetries?: number;
};

export class DWorkspace {
  public wsRoot: string;

  public onReady?: ({ ws }: { ws: DWorkspace }) => Promise<void>;

  static _WS: DWorkspace | undefined;

  static getOrCreate(ops?: { force: boolean }) {
    let justInitialized = false;
    if (!this._WS || ops?.force) {
      this._WS = new DWorkspace();
      justInitialized = true;
    }

    return { justInitialized, ws: this._WS };
  }

  static workspaceFile = vscode.workspace.workspaceFile;

  constructor() {
    const wsFile = DWorkspace.workspaceFile?.fsPath;
    if (!wsFile) {
      throw Error("wsFile is undefined");
    }

    this.wsRoot = wsFile;
  }

  async init(opts?: DWorkspaceInitOpts) {
    this.onReady = opts?.onReady;// register onReady callback
    // creawte server watcher and return
  }
}