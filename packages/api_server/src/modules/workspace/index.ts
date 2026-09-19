import {
  DEngineInitResp,
  EngineInitStatusResp,
  EngineState,
  error2PlainObject,
  ERROR_SEVERITY,
  NoteDictsUtils,
  WorkspaceInitRequest,
  WorkspaceRequest,
  WorkspaceSyncRequest,
} from "@saili/common-all";
import { SailEngine } from "@saili/engine-server";
import { getLogger } from "../../core";
import { getWSKey, getWSEngine, putWS } from "../../utils";
import { DConfig, getDurationMilliseconds } from "@saili/common-server";

export class WorkspaceController {
  static singleton?: WorkspaceController;
  static instance() {
    if (!WorkspaceController.singleton) {
      WorkspaceController.singleton = new WorkspaceController();
    }
    return WorkspaceController.singleton;
  }

  /**
   * Per-workspace init queues. Inits against the same workspace (and thus the
   * same engine instance) are serialized so that a full init never runs
   * concurrently with a minimal init or another full init.
   */
  private _initQueues: Map<string, Promise<unknown>>;

  constructor() {
    this._initQueues = new Map();
  }

  /**
   * Serialize `task` behind any previously enqueued task for `wsKey`.
   */
  private _enqueue<T>(wsKey: string, task: () => Promise<T>): Promise<T> {
    const prev = this._initQueues.get(wsKey) ?? Promise.resolve();
    const next = prev.then(task, task);
    // Keep the tail of the chain rejection-free so one failed init does not
    // poison the queue.
    this._initQueues.set(
      wsKey,
      next.catch(() => undefined)
    );
    return next;
  }

  async init(req: WorkspaceInitRequest): Promise<DEngineInitResp> {
    const { uri, mode, priorityPaths } = req;
    return this._enqueue(getWSKey(uri), () =>
      this._initImpl({ uri, mode, priorityPaths })
    );
  }

  private async _initImpl({
    uri,
    mode,
    priorityPaths,
  }: {
    uri: string;
    mode?: "minimal" | "full";
    priorityPaths?: string[];
  }): Promise<DEngineInitResp> {
    const start = process.hrtime();

    const ctx = "WorkspaceController:init";
    const logger = getLogger();
    logger.info({ ctx, msg: "enter", uri, mode });
    // Reuse the in-memory engine for this workspace when there is one (eg.
    // a minimal init was followed by a full init). Creating a new engine
    // would discard the warm state and any notes written while warm.
    let engine: SailEngine | undefined;
    try {
      engine = (await getWSEngine({ ws: uri })) as SailEngine;
    } catch (_err) {
      engine = undefined;
    }
    if (!engine) {
      engine = SailEngine.create({
        wsRoot: uri,
        logger,
      });
      // Register before initializing so concurrent requests (eg. initStatus
      // polls) can find the engine while it is still indexing.
      await putWS({ ws: uri, engine });
    }

    const resp =
      mode === "minimal"
        ? await engine.initMinimal({ priorityPaths })
        : await engine.init();
    const { data, error } = resp;
    if (error && error.severity === ERROR_SEVERITY.FATAL) {
      logger.error({ ctx, msg: "fatal error initializing notes", error });
      return { data, error };
    }

    // NOTE: the full index is intentionally NOT auto-continued here. The
    // client triggers `init` with mode "full" from its background
    // finish-activation step. That keeps a single full parse per startup
    // (a server-side background init + a later client init would parse the
    // whole vault twice) and lets the client's second init response carry
    // the full note set back for free. Readiness is observable via the
    // `/initStatus` endpoint in the meantime.

    const duration = getDurationMilliseconds(start);
    logger.info({ ctx, msg: "finish init", duration, uri, mode, error });
    let error2;
    if (error) {
      error2 = error2PlainObject(error);
    }
    const payload = {
      error: error2,
      data,
    };
    return payload;
  }

  /**
   * Current engine init status for a workspace. Used by clients during
   * fast-first startup to poll for the transition from warm to ready while
   * the full index runs in the background.
   */
  async initStatus({ ws }: WorkspaceRequest): Promise<EngineInitStatusResp> {
    const ctx = "WorkspaceController:initStatus";
    const logger = getLogger();
    try {
      const engine = await getWSEngine({ ws });
      const maybeState = (engine as Partial<SailEngine>).getEngineState;
      const state: EngineState =
        typeof maybeState === "function" ? maybeState.call(engine) : "ready";
      const maybeProgress = (engine as Partial<SailEngine>).getInitProgress;
      const progress =
        typeof maybeProgress === "function"
          ? maybeProgress.call(engine)
          : undefined;
      return { data: { state, progress } };
    } catch (_err) {
      // No engine registered for this workspace yet.
      logger.info({ ctx, msg: "no engine for workspace", ws });
      return { data: { state: "cold" } };
    }
  }

  async sync({ ws }: WorkspaceSyncRequest): Promise<DEngineInitResp> {
    const engine = await getWSEngine({ ws });
    const notes = await engine.findNotes({ excludeStub: false });
    return {
      data: {
        notes: NoteDictsUtils.createNotePropsByIdDict(notes),
        config: DConfig.readConfigSync(engine.wsRoot),
        vaults: engine.vaults,
        wsRoot: engine.wsRoot,
      },
    };
  }
}
