import "reflect-metadata";
import { SubProcessExitType } from "@saili/api-server";
import {
  CONSTANTS,
  SailError,
  DVault,
  DWorkspaceV2,
  ErrorFactory,
  getStage,
  GitEvents,
  RespV3,
  TreeViewItemLabelTypeEnum,
  VaultUtils,
  VSCodeEvents,
  WorkspaceType,
} from "@saili/common-all";
import { getDurationMilliseconds, GitUtils } from "@saili/common-server";
import {
  HistoryService,
  MetadataService,
  WorkspaceService,
  WorkspaceUtils,
} from "@saili/engine-server";
import _ from "lodash";
import path from "path";
import semver from "semver";
import * as vscode from "vscode";
import { SailContext, DENDRON_COMMANDS, WORKSPACE_STATE } from "../constants";
import { ISailExtension } from "../sailExtensionInterface";
import { Logger } from "../logger";
import { EngineAPIService } from "../services/EngineAPIService";
import { TextDocumentServiceFactory } from "../services/TextDocumentServiceFactory";
import { ExtensionUtils } from "../utils/ExtensionUtils";
import { StartupUtils } from "../utils/StartupUtils";
import { VSCodeUtils } from "../vsCodeUtils";
import { SailExtension } from "../workspace";
import { WSUtils } from "../WSUtils";
import { SailCodeWorkspace } from "./codeWorkspace";
import { SailNativeWorkspace } from "./nativeWorkspace";
import { WorkspaceInitFactory } from "./WorkspaceInitFactory";
import { WorkspaceInitializer } from "./workspaceInitializer";
import { CreateNoteCommand } from "../commands/CreateNoteCommand";
import { container } from "tsyringe";
import { NativeTreeView } from "../views/common/treeview/NativeTreeView";
import SparkMD5 from "spark-md5";

function _setupTreeViewCommands(
  treeView: NativeTreeView,
  existingCommands: string[]
) {
  if (
    !existingCommands.includes(DENDRON_COMMANDS.TREEVIEW_LABEL_BY_TITLE.key)
  ) {
    vscode.commands.registerCommand(
      DENDRON_COMMANDS.TREEVIEW_LABEL_BY_TITLE.key,
      () => {
        treeView.updateLabelType({
          labelType: TreeViewItemLabelTypeEnum.title,
        });
      }
    );
  }

  if (
    !existingCommands.includes(DENDRON_COMMANDS.TREEVIEW_LABEL_BY_FILENAME.key)
  ) {
    vscode.commands.registerCommand(
      DENDRON_COMMANDS.TREEVIEW_LABEL_BY_FILENAME.key,
      () => {
        treeView.updateLabelType({
          labelType: TreeViewItemLabelTypeEnum.filename,
        });
      }
    );
  }

  if (!existingCommands.includes(DENDRON_COMMANDS.TREEVIEW_CREATE_NOTE.key)) {
    vscode.commands.registerCommand(
      DENDRON_COMMANDS.TREEVIEW_CREATE_NOTE.key,
      async (opts) => {
        await new CreateNoteCommand().run(opts);
      }
    );
  }

  /**
   * This is a little flaky right now, but it works most of the time.
   * Leaving this for dev / debug purposes.
   * Enablement is set to be SailContext.DEV_MODE
   *
   * TODO: fix tree item register issue and flip the dev mode flag.
   */
  if (!existingCommands.includes(DENDRON_COMMANDS.TREEVIEW_EXPAND_ALL.key)) {
    vscode.commands.registerCommand(
      DENDRON_COMMANDS.TREEVIEW_EXPAND_ALL.key,
      async () => {
        await treeView.expandAll();
      }
    );
  }

  if (!existingCommands.includes(DENDRON_COMMANDS.TREEVIEW_EXPAND_STUB.key)) {
    vscode.commands.registerCommand(
      DENDRON_COMMANDS.TREEVIEW_EXPAND_STUB.key,
      async (id) => {
        await treeView.expandTreeItem(id);
      }
    );
  }
}

export function trackTopLevelRepoFound(opts: { wsService: WorkspaceService }) {
  const { wsService } = opts;
  return wsService.getTopLevelRemoteUrl().then((remoteUrl) => {
    if (remoteUrl !== undefined) {
      const [protocol, provider, ...path] = GitUtils.parseGitUrl(remoteUrl);
      const payload = {
        protocol: protocol.replace(":", ""),
        provider,
        path: SparkMD5.hash(`${path[0]}/${path[1]}.git`),
      };
      return payload;
    }
    return undefined;
  });
}

function analyzeWorkspace({ wsService }: { wsService: WorkspaceService }) {
  // Track contributors to repositories, but do so in the background so
  // initialization isn't delayed.
  const startGetAllReposNumContributors = process.hrtime();
  wsService
    .getAllReposNumContributors()
    .then((numContributors) => {
    })
    .catch((err) => {
      Logger.warn({ ctx: "workspaceActivator", msg: "Failed to get all repos num contributors", err });
    });
  trackTopLevelRepoFound({ wsService });
}

async function getOrPromptWSRoot(workspaceFolders: string[]) {
  if (!workspaceFolders) {
    Logger.error({ msg: "No sail.yml found in any workspace folder" });
    return undefined;
  }
  if (workspaceFolders.length === 1) {
    return workspaceFolders[0];
  } else {
    const selectedRoot = await VSCodeUtils.showQuickPick(
      workspaceFolders.map((folder): vscode.QuickPickItem => {
        return {
          label: folder,
        };
      }),
      {
        ignoreFocusOut: true,
        canPickMany: false,
        title: "Select Sail workspace to load",
      }
    );
    if (!selectedRoot) {
      await vscode.window.showInformationMessage(
        "You skipped loading any Sail workspace, Sail is not active. You can run the 'Developer: Reload Window' command to reactivate Sail."
      );
      Logger.info({
        msg: "User skipped loading a Sail workspace",
        workspaceFolders,
      });
      return null;
    }
    return selectedRoot.label;
  }
}

/**
 * Get version of Sail when workspace was last activated
 */
async function getAndCleanPreviousWSVersion({
  wsService,
  workspaceState,
  ext,
}: {
  workspaceState: vscode.Memento;
  wsService: WorkspaceService;
  ext: ISailExtension;
}) {
  let previousWorkspaceVersionFromWSService = wsService.getMeta().version;

  // Fix a temporary issue where CLI was writing an invalid version number
  // to .sail.ws:
  if (previousWorkspaceVersionFromWSService === "sail-cli") {
    previousWorkspaceVersionFromWSService = "0.91.0";
  }
  if (ext.type === WorkspaceType.NATIVE) {
    return previousWorkspaceVersionFromWSService;
  }

  // Code workspace specific code
  // Migration code: we used to store verion history in state vs metadata
  const previousWorkspaceVersionFromState =
    workspaceState.get<string>(WORKSPACE_STATE.VERSION) || "0.0.0";
  if (
    !semver.valid(previousWorkspaceVersionFromWSService) ||
    semver.gt(
      previousWorkspaceVersionFromState,
      previousWorkspaceVersionFromWSService
    )
  ) {
    previousWorkspaceVersionFromWSService = previousWorkspaceVersionFromState;
    wsService.writeMeta({ version: previousWorkspaceVersionFromState });
  }
  return previousWorkspaceVersionFromWSService;
}

async function checkNoDuplicateVaultNames(vaults: DVault[]): Promise<boolean> {
  // check for vaults with same name
  const uniqueVaults = new Set<string>();
  const duplicates = new Set<string>();
  vaults.forEach((vault) => {
    const vaultName = VaultUtils.getName(vault);
    if (uniqueVaults.has(vaultName)) duplicates.add(vaultName);
    uniqueVaults.add(vaultName);
  });

  if (duplicates.size > 0) {
    const txt = "Fix it";
    const duplicateVaultNames = Array.from(duplicates).join(", ");
    await vscode.window
      .showErrorMessage(
        `Following vault names have duplicates: ${duplicateVaultNames} See https://sail.so/notes/a6c03f9b-8959-4d67-8394-4d204ab69bfe.html#multiple-vaults-with-the-same-name to fix`,
        txt
      )
      .then((resp) => {
        if (resp === txt) {
          vscode.commands.executeCommand(
            "vscode.open",
            vscode.Uri.parse(
              "https://sail.so/notes/a6c03f9b-8959-4d67-8394-4d204ab69bfe.html#multiple-vaults-with-the-same-name"
            )
          );
        }
      });
    return false;
  }
  return true;
}

async function initTreeView({ context }: { context: vscode.ExtensionContext }) {
  const existingCommands = await vscode.commands.getCommands();
  const treeView = container.resolve(NativeTreeView);
  treeView.show();
  _setupTreeViewCommands(treeView, existingCommands);
  context.subscriptions.push(treeView);
}

async function postReloadWorkspace({
  wsService,
}: {
  wsService: WorkspaceService;
}) {
  const ctx = "postReloadWorkspace";
  if (!wsService) {
    const errorMsg = "No workspace service found.";
    Logger.error({
      msg: errorMsg,
      error: new SailError({ message: errorMsg }),
    });
    return;
  }

  const wsMeta = wsService.getMeta();
  const previousWsVersion = wsMeta.version;
  // stats
  // NOTE: this is legacy to upgrade .code-workspace specific settings
  // we are moving everything to sail.yml
  // see [[2021 06 Deprecate Workspace Settings|proj.2021-06-deprecate-workspace-settings]]
  if (previousWsVersion === CONSTANTS.DENDRON_INIT_VERSION) {
    Logger.info({ ctx, msg: "no previous global version" });
    vscode.commands
      .executeCommand(DENDRON_COMMANDS.UPGRADE_SETTINGS.key)
      .then((changes) => {
        Logger.info({ ctx, msg: "postUpgrade: new wsVersion", changes });
      });
    wsService.writeMeta({ version: SailExtension.version() });
  } else {
    const newVersion = SailExtension.version();
    if (semver.lt(previousWsVersion, newVersion)) {
      let changes: any;
      Logger.info({ ctx, msg: "preUpgrade: new wsVersion" });
      try {
        changes = await vscode.commands.executeCommand(
          DENDRON_COMMANDS.UPGRADE_SETTINGS.key
        );
        Logger.info({
          ctx,
          msg: "postUpgrade: new wsVersion",
          changes,
          previousWsVersion,
          newVersion,
        });
        wsService.writeMeta({ version: SailExtension.version() });
      } catch (err) {
        Logger.error({
          msg: "error upgrading",
          error: new SailError({ message: JSON.stringify(err) }),
        });
        return;
      }
      HistoryService.instance().add({
        source: "extension",
        action: "upgraded",
        data: { changes },
      });
    } else {
      Logger.info({ ctx, msg: "same wsVersion" });
    }
  }
  Logger.info({ ctx, msg: "exit" });
}

async function reloadWorkspace({
  ext,
  wsService,
}: {
  ext: ISailExtension;
  wsService: WorkspaceService;
}) {
  const ctx = "reloadWorkspace";
  const ws = ext.getDWorkspace();
  const maybeEngine = await WSUtils.instance().reloadWorkspace();
  if (!maybeEngine) {
    return maybeEngine;
  }
  Logger.info({ ctx, msg: "post-ws.reloadWorkspace" });

  // Run any initialization code necessary for this workspace invocation.
  const initializer = WorkspaceInitFactory.create();

  if (initializer?.onWorkspaceOpen) {
    initializer.onWorkspaceOpen({ ws });
  }

  vscode.window.showInformationMessage("Sail is active");
  Logger.info({ ctx, msg: "exit" });

  await postReloadWorkspace({ wsService });
  HistoryService.instance().add({
    source: "extension",
    action: "initialized",
  });
  return maybeEngine;
}

function togglePluginActiveContext(enabled: boolean) {
  const ctx = "togglePluginActiveContext";
  Logger.info({ ctx, state: `togglePluginActiveContext: ${enabled}` });
  VSCodeUtils.setContext(SailContext.PLUGIN_ACTIVE, enabled);
  VSCodeUtils.setContext(SailContext.HAS_CUSTOM_MARKDOWN_VIEW, enabled);
}

function updateEngineAPI(
  port: number | string,
  ext: ISailExtension
): EngineAPIService {
  // set engine api ^9dr6chh7ah9v
  const svc = EngineAPIService.createEngine({
    port,
    enableWorkspaceTrust: vscode.workspace.isTrusted,
    vaults: ext.getDWorkspace().vaults,
    wsRoot: ext.getDWorkspace().wsRoot,
  });
  ext.setEngine(svc);
  ext.port = _.toInteger(port);

  return svc;
}

type WorkspaceActivatorValidateOpts = {
  ext: ISailExtension;
  context: vscode.ExtensionContext;
};

type WorkspaceActivatorOpts = {
  ext: ISailExtension;
  context: vscode.ExtensionContext;
  wsRoot: string;
  workspaceInitializer?: WorkspaceInitializer;
};

type WorkspaceActivatorSkipOpts = {
  opts?: Partial<{
    /**
     * Skip setting up language features (eg. code action providesr)
     */
    skipLanguageFeatures: boolean;
    /**
     * Skip automatic migrations on start
     */
    skipMigrations: boolean;
    /**
     * Skip surfacing dialogues on startup
     */
    skipInteractiveElements: boolean;

    /**
     * Skip showing tree view
     */
    skipTreeView: boolean;
  }>;
};
export class WorkspaceActivator {
  /**
   * Initialize workspace. All logic that happens before the engine is initialized happens here
   * - create workspace class
   * - register traits
   * - run migrations if necessary
   */
  async init({
    ext,
    context,
    wsRoot,
    opts,
  }: WorkspaceActivatorOpts & WorkspaceActivatorSkipOpts): Promise<
    RespV3<{
      workspace: DWorkspaceV2;
      engine: EngineAPIService;
      wsService: WorkspaceService;
    }>
  > {
    const ctx = "WorkspaceActivator.init";
    // --- Setup workspace
    let workspace: DWorkspaceV2;
    if (ext.type === WorkspaceType.NATIVE) {
      workspace = await this.initNativeWorkspace({ ext, context, wsRoot });
      if (!workspace) {
        return {
          error: ErrorFactory.createInvalidStateError({
            message: "could not find native workspace",
          }),
        };
      }
    } else {
      workspace = await this.initCodeWorkspace({ ext, context, wsRoot });
    }

    ext.workspaceImpl = workspace;
    // HACK: Only set up note traits after workspaceImpl has been set, so that
    // the wsRoot path is known for locating the note trait definition location.
    if (vscode.workspace.isTrusted) {
      ext.traitRegistrar.initialize();
    } else {
      Logger.info({
        msg: "User specified note traits not initialized because workspace is not trusted.",
      });
    }

    // --- Initialization
    Logger.info({ ctx: `${ctx}:postSetupTraits`, wsRoot });
    const currentVersion = SailExtension.version();
    const wsService = new WorkspaceService({ wsRoot });
    const sailConfig = workspace.config;
    ext.workspaceService = wsService;

    // get previous workspace version and fixup
    const previousWorkspaceVersion = await getAndCleanPreviousWSVersion({
      wsService,
      workspaceState: context.workspaceState,
      ext,
    });

    // run migrations
    const maybeWsSettings =
      ext.type === WorkspaceType.CODE
        ? wsService.getCodeWorkspaceSettingsSync()
        : undefined;
    if (!opts?.skipMigrations) {
      await StartupUtils.showManualUpgradeMessageIfNecessary({
        previousWorkspaceVersion,
        currentVersion,
      });

      await StartupUtils.runMigrationsIfNecessary({
        wsService,
        currentVersion,
        previousWorkspaceVersion,
        maybeWsSettings,
        sailConfig,
      });
    }
    Logger.info({ ctx: `${ctx}:postMigration`, wsRoot });

    // show interactive elements,
    if (!opts?.skipInteractiveElements) {
      // check for duplicate config keys and prompt for a fix.
      StartupUtils.showDuplicateConfigEntryMessageIfNecessary({
        ext,
      });
    }

    // initialize vaults, clone remote vaults if needed
    const didClone = await wsService.initialize({
      onSyncVaultsProgress: () => {
        vscode.window.showInformationMessage(
          "found empty remote vaults that need initializing"
        );
      },
      onSyncVaultsEnd: () => {
        vscode.window.showInformationMessage(
          "finish initializing remote vaults. reloading workspace"
        );
        // TODO: remove
        setTimeout(VSCodeUtils.reloadWindow, 200);
      },
    });
    if (didClone) {
      return {
        error: ErrorFactory.createInvalidStateError({
          message: "could not initialize workspace",
        }),
      };
    }
    Logger.info({ ctx: `${ctx}:postWsServiceInitialize`, wsRoot });

    // check for vaults with duplicates
    const respNoDupVault = await checkNoDuplicateVaultNames(wsService.vaults);
    if (!respNoDupVault) {
      return {
        error: ErrorFactory.createInvalidStateError({
          message: "found duplicate vaults",
        }),
      };
    }

    // write new workspace version
    wsService.writeMeta({ version: SailExtension.version() });

    // setup engine
    const port = await this.verifyOrStartServerProcess({ ext, wsService });
    Logger.info({ ctx: `${ctx}:verifyOrStartServerProcess`, port });
    const engine = updateEngineAPI(port, ext);
    Logger.info({ ctx: `${ctx}:exit` });

    return { data: { workspace, engine, wsService } };
  }

  /**
   * Initialize engine and activate workspace watchers
   */
  async activate({
    ext,
    context,
    wsService,
    wsRoot,
    opts,
    workspaceInitializer,
  }: WorkspaceActivatorOpts &
    WorkspaceActivatorSkipOpts & {
      engine: EngineAPIService;
      wsService: WorkspaceService;
    }): Promise<RespV3<boolean>> {
    const ctx = "WorkspaceActivator:activate";
    // setup services
    context.subscriptions.push(TextDocumentServiceFactory.create(ext));

    // Reload
    WSUtils.instance().showActivateProgress();
    const start = process.hrtime();
    const reloadSuccess = await reloadWorkspace({ ext, wsService });
    const durationReloadWorkspace = getDurationMilliseconds(start);

    // NOTE: tracking is not awaited, don't block on this
    ExtensionUtils.trackWorkspaceInit({
      durationReloadWorkspace,
      activatedSuccess: !!reloadSuccess,
      ext,
    }).catch((error) => {
      Logger.warn({ ctx: "workspaceActivator", msg: "Failed to track duration", error });
    });

    analyzeWorkspace({ wsService });

    if (!reloadSuccess) {
      HistoryService.instance().add({
        source: "extension",
        action: "not_initialized",
      });
      return {
        error: ErrorFactory.createInvalidStateError({
          message: `issue with init`,
        }),
      };
    }

    ExtensionUtils.setWorkspaceContextOnActivate(wsService.config);
    MetadataService.instance().setSailWorkspaceActivated();
    Logger.info({ ctx, msg: "fin startClient", durationReloadWorkspace });

    const stage = getStage();
    if (stage !== "test") {
      ext.activateWatchers();
      togglePluginActiveContext(true);
    }

    // Setup tree view
    // This needs to happen after activation because we need the engine.
    if (!opts?.skipTreeView) {
      await initTreeView({
        context,
      });
    }

    // Add the current workspace to the recent workspace list. The current
    // workspace is either the workspace file (Code Workspace) or the current
    // folder (Native Workspace)
    const workspace = SailExtension.tryWorkspaceFile()?.fsPath || wsRoot;
    MetadataService.instance().addToRecentWorkspaces(workspace);

    if (workspaceInitializer?.onWorkspaceActivate) {
      workspaceInitializer.onWorkspaceActivate({
        skipOpts: opts,
      });
    } else {
      const initializer = WorkspaceInitFactory.create();
      if (initializer && initializer.onWorkspaceActivate) {
        initializer.onWorkspaceActivate({
          skipOpts: opts,
        });
      }
    }
    return { data: true };
  }

  async initCodeWorkspace({ context, wsRoot }: WorkspaceActivatorOpts) {
    const assetUri = VSCodeUtils.getAssetUri(context);
    const ws = new SailCodeWorkspace({
      wsRoot,
      logUri: context.logUri,
      assetUri,
    });
    return ws;
  }

  async initNativeWorkspace({ context, wsRoot }: WorkspaceActivatorOpts) {
    const assetUri = VSCodeUtils.getAssetUri(context);
    const ws = new SailNativeWorkspace({
      wsRoot,
      logUri: context.logUri,
      assetUri,
    });
    return ws;
  }

  async getOrPromptWsRoot({
    ext,
  }: WorkspaceActivatorValidateOpts): Promise<string | undefined> {
    if (ext.type === WorkspaceType.NATIVE) {
      const workspaceFolders =
        await WorkspaceUtils.findWSRootsInWorkspaceFolders(
          SailExtension.workspaceFolders()!
        );
      if (!workspaceFolders) {
        return;
      }
      const resp = await getOrPromptWSRoot(workspaceFolders);
      if (!_.isString(resp)) {
        return;
      }
      return resp;
    } else {
      return path.dirname(SailExtension.workspaceFile().fsPath);
    }
  }

  /**
   * Return true if we started a server process
   * @returns
   */
  async verifyOrStartServerProcess({
    ext,
    wsService,
  }: {
    ext: ISailExtension;
    wsService: WorkspaceService;
  }): Promise<number> {
    const context = ext.context;
    const start = process.hrtime();
    if (ext.port) {
      return ext.port;
    }

    const { port, subprocess } = await ExtensionUtils.startServerProcess({
      context,
      start,
      wsService,
      onExit: (type: SubProcessExitType) => {
        const txt = "Restart Sail";
        vscode.window
          .showErrorMessage("Sail engine encountered an error", txt)
          .then(async (resp) => {
            if (resp === txt) {
              await ExtensionUtils.activate();
            }
          });
      },
    });
    ext.port = _.toInteger(port);
    ext.serverProcess = subprocess;
    return ext.port;
  }
}

