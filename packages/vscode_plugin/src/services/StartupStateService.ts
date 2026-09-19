import { EngineState, ENGINE_STATE } from "@saili/common-all";
import * as vscode from "vscode";
import { Logger } from "../logger";

/**
 * Client-side mirror of the engine state machine (cold → warm → ready) for
 * the current activation.
 *
 * The extension activates in three stages:
 * 1. cold — engine server is starting, nothing is usable yet.
 * 2. warm — schemas + priority notes parsed, stubs registered; the daily
 *    journal path (create/open today) is usable.
 * 3. ready — full note index complete; watchers, tree view and the rest of
 *    the plugin surface turn on.
 *
 * This service is the single source of truth for which stage the extension
 * is in. It backs the `sail:engineWarm` / `sail:starting` context keys, the
 * status bar indexing indicator and the WARM-period command guard.
 */
export class StartupStateService implements vscode.Disposable {
  private static _instance?: StartupStateService;

  static instance(): StartupStateService {
    if (!StartupStateService._instance) {
      StartupStateService._instance = new StartupStateService();
    }
    return StartupStateService._instance;
  }

  /** Test-only: reset the singleton. */
  static reset() {
    StartupStateService._instance?.dispose();
    StartupStateService._instance = undefined;
  }

  private _state: EngineState = ENGINE_STATE.COLD;
  private _cancelled = false;
  private _onDidChangeEngineStateEmitter: vscode.EventEmitter<EngineState>;

  readonly onDidChangeEngineState: vscode.Event<EngineState>;

  private constructor() {
    this._onDidChangeEngineStateEmitter = new vscode.EventEmitter<EngineState>();
    this.onDidChangeEngineState = this._onDidChangeEngineStateEmitter.event;
  }

  get state(): EngineState {
    return this._state;
  }

  /**
   * True once the engine has reached the warm state (or beyond). The daily
   * journal path is usable from this point on.
   */
  get isWarm(): boolean {
    return this._state === ENGINE_STATE.WARM || this._state === ENGINE_STATE.READY;
  }

  get isReady(): boolean {
    return this._state === ENGINE_STATE.READY;
  }

  /**
   * Set when the extension is being deactivated while a background
   * finish-activation is still in flight. Long-running startup work should
   * check this flag and abort quietly.
   */
  get cancelled(): boolean {
    return this._cancelled;
  }

  setState(state: EngineState) {
    if (state === this._state) {
      return;
    }
    const ctx = "StartupStateService:setState";
    Logger.info({ ctx, from: this._state, to: state });
    this._state = state;
    this._onDidChangeEngineStateEmitter.fire(state);
  }

  /**
   * Cancel any in-flight startup work. Called from `deactivate()`.
   */
  cancel() {
    this._cancelled = true;
  }

  /**
   * Resolve once the engine is at least warm, or immediately if it already
   * is. Rejects after `timeoutMs` so callers can surface a friendly message
   * instead of hanging forever.
   */
  async waitForWarm(timeoutMs: number = 30_000): Promise<void> {
    if (this.isWarm) {
      return;
    }
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        disposable.dispose();
        reject(
          new Error(
            `Timed out waiting for Sail engine to warm up (state: ${this._state})`
          )
        );
      }, timeoutMs);
      const disposable = this.onDidChangeEngineState((state) => {
        if (state === ENGINE_STATE.WARM || state === ENGINE_STATE.READY) {
          clearTimeout(timer);
          disposable.dispose();
          resolve();
        }
      });
    });
  }

  dispose() {
    this._onDidChangeEngineStateEmitter.dispose();
  }
}
