import "reflect-metadata";
import { SubProcessExitType } from "@saili/api-server";
import {
  CONSTANTS,
  SailError,
  ConfigUtils,
  DVault,
  DWorkspaceV2,
  ENGINE_STATE,
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
import { SailContext, SAIL_COMMANDS, WORKSPACE_STATE } from "../constants";
import { SailClientUtils } from "../clientUtils";
import { ISailExtension } from "../sailExtensionInterface";
import { Logger } from "../logger";
import { StartupProfiler } from "../perf/StartupProfiler";
import { EngineAPIService } from "../services/EngineAPIService";
import { StartupStateService } from "../services/StartupStateService";
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
    !existingCommands.includes(SAIL_COMMANDS.TREEVIEW_LABEL_BY_TITLE.key)
  ) {
    vscode.commands.registerCommand(
      SAIL_COMMANDS.TREEVIEW_LABEL_BY_TITLE.key,
      () => {
        treeView.updateLabelType({
          labelType: TreeViewItemLabelTypeEnum.title,
        });
      }
    );
  }

  if (
    !existingCommands.includes(SAIL_COMMANDS.TREEVIEW_LABEL_BY_FILENAME.key)
  ) {
    vscode.commands.registerCommand(
      SAIL_COMMANDS.TREEVIEW_LABEL_BY_FILENAME.key,
      () => {
        treeView.updateLabelType({
          labelType: TreeViewItemLabelTypeEnum.filename,
        });
      }
    );
  }

  if (!existingCommands.includes(SAIL_COMMANDS.TREEVIEW_CREATE_NOTE.key)) {
    vscode.commands.registerCommand(
      SAIL_COMMANDS.TREEVIEW_CREATE_NOTE.key,
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
  if (!existingCommands.includes(SAIL_COMMANDS.TREEVIEW_EXPAND_ALL.key)) {
    vscode.commands.registerCommand(
      SAIL_COMMANDS.TREEVIEW_EXPAND_ALL.key,
      async () => {
        await treeView.expandAll();
      }
    );
  }

  if (!existingCommands.includes(SAIL_COMMANDS.TREEVIEW_EXPAND_STUB.key)) {
    vscode.commands.registerCommand(
      SAIL_COMMANDS.TREEVIEW_EXPAND_STUB.key,
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
  if (previousWsVersion === CONSTANTS.SAIL_INIT_VERSION) {
    Logger.info({ ctx, msg: "no previous global version" });
    vscode.commands
      .executeCommand(SAIL_COMMANDS.UPGRADE_SETTINGS.key)
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
          SAIL_COMMANDS.UPGRADE_SETTINGS.key
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
  mode = "full",
  priorityPaths,
}: {
  ext: ISailExtension;
  wsService: WorkspaceService;
  mode?: "minimal" | "full";
  priorityPaths?: string[];
}) {
  const ctx = "reloadWorkspace";
  const ws = ext.getDWorkspace();
  const maybeEngine = await WSUtils.instance().reloadWorkspace({
    mode,
    priorityPaths,
  });
  if (!maybeEngine) {
    return maybeEngine;
  }
  Logger.info({ ctx, msg: "post-ws.reloadWorkspace", mode });

  // Run any initialization code necessary for this workspace invocation.
  const initializer = WorkspaceInitFactory.create();

  if (initializer?.onWorkspaceOpen) {
    initializer.onWorkspaceOpen({ ws });
  }

  vscode.window.showInformationMessage("Sail is active");
  Logger.info({ ctx, msg: "exit" });

  if (mode === "minimal") {
    // Fast-first startup: the workspace upgrade check and the
    // `initialized` history event are deferred to `finishActivation`, which
    // runs once the full index is complete. This keeps the warm-state
    // activation minimal.
    return maybeEngine;
  }

  await postReloadWorkspace({ wsService });
  HistoryService.instance().add({
    source: "extension",
    action: "initialized",
  });
  return maybeEngine;
}

/**
 * Compute the note fnames to fully parse during a minimal (warm) init:
 * today's daily journal and the daily journal template. Everything else on
 * disk is registered as a lightweight stub. Best effort — returns an empty
 * list if the journal config is missing or malformed.
 */
function getWarmPriorityPaths(ext: ISailExtension): string[] {
  const ctx = "getWarmPriorityPaths";
  try {
    const config = ext.getDWorkspace().config;
    const journalConfig = ConfigUtils.getJournal(config);
    const prefix = SailClientUtils.genNotePrefix(
      journalConfig.name,
      journalConfig.addBehavior
    );
    const noteDate = SailClientUtils.getTodayDateForStartup(journalConfig);
    const todayJournalFname = [prefix, journalConfig.dailyDomain, noteDate]
      .filter((ent) => !_.isEmpty(ent))
      .join(".");
    const templateFname = `templates.${journalConfig.dailyDomain}`;
    return [todayJournalFname, templateFname];
  } catch (err) {
    Logger.warn({
      ctx,
      msg: "unable to compute warm priority paths; warm init will stub everything",
      err,
    });
    return [];
  }
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
   * Resolves the two-phase "Starting Sail..." progress notification once the
   * engine reaches the warm state. Only set during `_activateWarm`.
   */
  private _warmResolve?: () => void;

  /**
   * Start of the fast-first activation, used to report the total
   * warm + full init duration for tracking.
   */
  private _activateStart?: [number, number];

  /**
   * When migrations are deferred (see `sail.startup.deferMigrations`), the
   * arguments needed to run them in `finishActivation` are stashed here.
   */
  private _deferredMigrationArgs?: {
    wsService: WorkspaceService;
    currentVersion: string;
    previousWorkspaceVersion: string;
    maybeWsSettings: ReturnType<WorkspaceService["getCodeWorkspaceSettingsSync"]>;
    sailConfig: DWorkspaceV2["config"];
  };

  /**
   * Initialize workspace. All logic that happens before the engine is initialized happens here
   * - create workspace class
   * - register traits
   * - run migrations if necessary
   */
  async init(
    opts: WorkspaceActivatorOpts & WorkspaceActivatorSkipOpts
  ): Promise<
    RespV3<{
      workspace: DWorkspaceV2;
      engine: EngineAPIService;
      wsService: WorkspaceService;
    }>
  > {
    const startWsInit = process.hrtime();
    try {
      return await this._initImpl(opts);
    } finally {
      StartupProfiler.recordSegmentSince("wsInit", startWsInit);
    }
  }

  private async _initImpl({
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
    const deferMigrations =
      StartupUtils.getDeferMigrations() &&
      WorkspaceActivator._useFastStartup();
    if (!opts?.skipMigrations && !deferMigrations) {
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
    } else if (!opts?.skipMigrations && deferMigrations) {
      // Fast-first startup: run migrations in the background
      // finish-activation step instead of blocking the warm path.
      this._deferredMigrationArgs = {
        wsService,
        currentVersion,
        previousWorkspaceVersion,
        maybeWsSettings,
        sailConfig,
      };
    }
    Logger.info({ ctx: `${ctx}:postMigration`, wsRoot, deferMigrations });

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
   * True when the fast-first (three stage) startup path should be used.
   * Legacy `"full"` mode and the test stage keep the original blocking
   * activation.
   */
  private static _useFastStartup(): boolean {
    return StartupUtils.getStartupMode() === "fast" && getStage() !== "test";
  }

  /**
   * Initialize engine and activate workspace watchers.
   *
   * Fast-first startup (`sail.startup.mode: "fast"`, default): returns as
   * soon as the engine is warm (schemas + priority notes parsed, stubs
   * registered). The caller then runs `finishActivation` in the background
   * to complete the full index and turn on the rest of the plugin.
   *
   * Legacy `"full"` mode (and the test stage): blocks until the full index
   * is built, preserving the original behavior.
   */
  async activate({
    ext,
    context,
    wsService,
    wsRoot,
    opts,
    workspaceInitializer,
    engine,
  }: WorkspaceActivatorOpts &
    WorkspaceActivatorSkipOpts & {
      engine: EngineAPIService;
      wsService: WorkspaceService;
    }): Promise<RespV3<boolean>> {
    if (!WorkspaceActivator._useFastStartup()) {
      return this._activateFull({
        ext,
        context,
        wsService,
        wsRoot,
        opts,
        workspaceInitializer,
        engine,
      });
    }
    return this._activateWarm({
      ext,
      context,
      wsService,
      wsRoot,
      opts,
      workspaceInitializer,
      engine,
    });
  }

  /**
   * Legacy blocking activation: full engine index before returning, then
   * watchers/tree view/tracking, exactly as before the fast-first refactor.
   */
  private async _activateFull({
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
    const reloadWorkspaceMode: "minimal" | "full" = "full";
    const reloadSuccess = await reloadWorkspace({
      ext,
      wsService,
      mode: reloadWorkspaceMode,
    });
    const durationReloadWorkspace = getDurationMilliseconds(start);
    if (!reloadSuccess) {
      // NOTE: tracking is not awaited, don't block on this
      ExtensionUtils.trackWorkspaceInit({
        durationReloadWorkspace,
        activatedSuccess: false,
        ext,
        startupMode: "full",
      }).catch((error) => {
        Logger.warn({ ctx: "workspaceActivator", msg: "Failed to track duration", error });
      });
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
      Logger.info({ ctx, msg: "fin startClient", durationReloadWorkspace });
      return this._completeActivation({
        ext,
        context,
        wsService,
        wsRoot,
        opts,
        workspaceInitializer,
        startupMode: "full",
        durationTotal: durationReloadWorkspace,
      });
    }

  /**
   * Shared activation tail: tracking, workspace analysis, watchers, plugin
   * context keys, tree view and workspace initializer hooks. Runs at the
   * ready stage for both the legacy full path and the fast-first path.
   */
  private async _completeActivation({
    ext,
    context,
    wsService,
    wsRoot,
    opts,
    workspaceInitializer,
    startupMode,
    durationTotal,
  }: WorkspaceActivatorOpts &
    WorkspaceActivatorSkipOpts & {
      wsService: WorkspaceService;
      startupMode: "fast" | "full";
      durationTotal: number;
    }): Promise<RespV3<boolean>> {
    const ctx = "WorkspaceActivator:completeActivation";
    ExtensionUtils.setWorkspaceContextOnActivate(wsService.config);
    VSCodeUtils.setContext(SailContext.ENGINE_WARM, true);
    StartupStateService.instance().setState(ENGINE_STATE.READY);
    VSCodeUtils.setContext(SailContext.STARTING, false);
    MetadataService.instance().setSailWorkspaceActivated();
    Logger.info({ ctx, msg: "fin startClient", durationTotal, startupMode });

    // NOTE: tracking is not awaited, don't block on this
    ExtensionUtils.trackWorkspaceInit({
      durationReloadWorkspace: durationTotal,
      activatedSuccess: true,
      ext,
      startupMode,
    }).catch((error) => {
      Logger.warn({ ctx, msg: "Failed to track duration", error });
    });

    analyzeWorkspace({ wsService });

    const stage = getStage();
    if (stage !== "test") {
      ext.activateWatchers();
      togglePluginActiveContext(true);
    }

    // Setup tree view
    // This needs to happen after activation because we need the engine.
    if (!opts?.skipTreeView) {
      const startTreeViewInit = process.hrtime();
      await initTreeView({
        context,
      });
      StartupProfiler.recordSegmentSince("treeViewInit", startTreeViewInit);
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

  /**
   * Stage 1 of fast-first startup: bring the engine to the warm state and
   * return immediately. The daily journal path (create/open today) is usable
   * from here on; the full note index is still building in the background.
   */
  private async _activateWarm({
    ext,
    context,
    wsService,
    wsRoot,
    opts,
    workspaceInitializer,
    engine,
  }: WorkspaceActivatorOpts &
    WorkspaceActivatorSkipOpts & {
      engine: EngineAPIService;
      wsService: WorkspaceService;
    }): Promise<RespV3<boolean>> {
    const ctx = "WorkspaceActivator:activateWarm";
    VSCodeUtils.setContext(SailContext.STARTING, true);
    // setup services
    context.subscriptions.push(TextDocumentServiceFactory.create(ext));

    // Two-phase progress notification: dismiss "Starting Sail..." as soon
    // as the engine is warm instead of waiting for the full index.
    const warmReached = new Promise<void>((resolve) => {
      this._warmResolve = resolve;
    });
    WSUtils.instance().showActivateProgress({ onWarm: warmReached });

    this._activateStart = process.hrtime();
    const priorityPaths = getWarmPriorityPaths(ext);
    const start = process.hrtime();
    const reloadSuccess = await reloadWorkspace({
      ext,
      wsService,
      mode: "minimal",
      priorityPaths,
    });
    const durationReloadWorkspace = getDurationMilliseconds(start);

    if (!reloadSuccess) {
      VSCodeUtils.setContext(SailContext.STARTING, false);
      HistoryService.instance().add({
        source: "extension",
        action: "not_initialized",
      });
      this._warmResolve = undefined;
      return {
        error: ErrorFactory.createInvalidStateError({
          message: `issue with init`,
        }),
      };
    }

      // Old-server degradation (P2-7): a server without minimal-init support
      // ignores `mode` and runs a full init, reporting `ready`. Detect this
      // and complete activation inline with legacy semantics instead of
      // pretending the engine is merely warm.
      if (engine.getEngineState() === ENGINE_STATE.READY) {
        Logger.warn({
          ctx,
          msg: "server does not support minimal init (no engineState in response); degrading to full-mode activation",
        });
        // Dismiss the two-phase progress notification and fire the history
        // event subscribers (webview providers) expect.
        const resolveWarm = this._warmResolve;
        this._warmResolve = undefined;
        resolveWarm?.();
        HistoryService.instance().add({
          source: "extension",
          action: "initialized",
        });
        return this._completeActivation({
          ext,
          context,
          wsService,
          wsRoot,
          opts,
          workspaceInitializer,
          startupMode: "full",
          durationTotal: durationReloadWorkspace,
        });
      }

      Logger.info({ ctx, msg: "engine warm", durationReloadWorkspace });
      VSCodeUtils.setContext(SailContext.ENGINE_WARM, true);
      StartupStateService.instance().setState(ENGINE_STATE.WARM);
      const resolveWarm = this._warmResolve;
      this._warmResolve = undefined;
      resolveWarm?.();

      ExtensionUtils.setWorkspaceContextOnActivate(wsService.config);
      MetadataService.instance().setSailWorkspaceActivated();

      // NOTE: tracking (trackWorkspaceInit) and analyzeWorkspace are deferred
      // to finishActivation so they don't compete with the warm-state journal
      // path for CPU/IO (see P2-6).
      return { data: true };
    }

  /**
   * Stage 2 of fast-first startup. Runs in the background after
   * {@link WorkspaceActivator.activate} returns warm: triggers the full
   * index (the response also syncs the full note set back to the client),
   * then turns on watchers, the tree view and the remaining plugin surface.
   *
   * Failures are reported through the `not_initialized` history event,
   * matching the legacy activation error semantics.
   */
  async finishActivation({
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
    const ctx = "WorkspaceActivator:finishActivation";
    try {
      // Deferred migrations (fast-first startup): run before the full index
      // so config changes are picked up by the full re-index.
      if (this._deferredMigrationArgs && !StartupStateService.instance().cancelled) {
        const args = this._deferredMigrationArgs;
        this._deferredMigrationArgs = undefined;
        await StartupUtils.showManualUpgradeMessageIfNecessary({
          previousWorkspaceVersion: args.previousWorkspaceVersion,
          currentVersion: args.currentVersion,
        });
        await StartupUtils.runMigrationsIfNecessary({
          wsService: args.wsService,
          currentVersion: args.currentVersion,
          previousWorkspaceVersion: args.previousWorkspaceVersion,
          maybeWsSettings: args.maybeWsSettings,
          sailConfig: args.sailConfig,
        });
      }

      // Trigger the full index. The server serializes it behind the warm
      // init, and the response carries the full note set back to the client,
      // which refreshes lookup/tree via synthetic create events.
      const reloadSuccess = await reloadWorkspace({
        ext,
        wsService,
        mode: "full",
      });

      if (StartupStateService.instance().cancelled) {
        return { data: false };
      }

      if (!reloadSuccess) {
        VSCodeUtils.setContext(SailContext.STARTING, false);
        HistoryService.instance().add({
          source: "extension",
          action: "not_initialized",
        });
        return {
          error: ErrorFactory.createInvalidStateError({
            message: `issue with full init`,
          }),
        };
      }

      Logger.info({ ctx, msg: "engine ready" });

      const durationTotal = this._activateStart
        ? getDurationMilliseconds(this._activateStart)
        : 0;

      return this._completeActivation({
        ext,
        context,
        wsService,
        wsRoot,
        opts,
        workspaceInitializer,
        startupMode: "fast",
        durationTotal,
      });
    } catch (err) {
      Logger.error({ ctx, error: err as any });
      VSCodeUtils.setContext(SailContext.STARTING, false);
      HistoryService.instance().add({
        source: "extension",
        action: "not_initialized",
        data: { err },
      });
      return {
        error: ErrorFactory.createInvalidStateError({
          message: `issue with finishActivation`,
        }),
      };
    }
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

