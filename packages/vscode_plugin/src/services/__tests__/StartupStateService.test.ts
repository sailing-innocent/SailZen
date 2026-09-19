/**
 * Tests for the client-side startup state machine (cold → warm → ready)
 * backing the fast-first startup flow: context keys, the status bar indexing
 * indicator and the WARM-period command guard all read this service.
 */
import { jest } from "@jest/globals";
import { ENGINE_STATE } from "@saili/common-all";

// The logger pulls in the full vscode/FileItem chain; keep this unit test
// focused on the state machine.
jest.unstable_mockModule("../../logger", () => ({
  Logger: { info: jest.fn() },
}));

const { StartupStateService } = await import("../StartupStateService");

describe("GIVEN StartupStateService", () => {
  beforeEach(() => {
    StartupStateService.reset();
  });
  afterEach(() => {
    StartupStateService.reset();
  });

  test("WHEN created THEN state is cold and not warm/ready", () => {
    const svc = StartupStateService.instance();
    expect(svc.state).toEqual(ENGINE_STATE.COLD);
    expect(svc.isWarm).toBe(false);
    expect(svc.isReady).toBe(false);
    expect(svc.cancelled).toBe(false);
  });

  test("WHEN state transitions to warm THEN isWarm is true, isReady false and listeners fire", () => {
    const svc = StartupStateService.instance();
    const seen: string[] = [];
    svc.onDidChangeEngineState((state) => seen.push(state));
    svc.setState(ENGINE_STATE.WARM);
    expect(svc.state).toEqual(ENGINE_STATE.WARM);
    expect(svc.isWarm).toBe(true);
    expect(svc.isReady).toBe(false);
    expect(seen).toEqual([ENGINE_STATE.WARM]);
  });

  test("WHEN state transitions to ready THEN isReady is true", () => {
    const svc = StartupStateService.instance();
    svc.setState(ENGINE_STATE.WARM);
    svc.setState(ENGINE_STATE.READY);
    expect(svc.state).toEqual(ENGINE_STATE.READY);
    expect(svc.isWarm).toBe(true);
    expect(svc.isReady).toBe(true);
  });

  test("WHEN setState is called with the current state THEN no event fires", () => {
    const svc = StartupStateService.instance();
    svc.setState(ENGINE_STATE.WARM);
    const seen: string[] = [];
    svc.onDidChangeEngineState((state) => seen.push(state));
    svc.setState(ENGINE_STATE.WARM);
    expect(seen).toEqual([]);
  });

  test("WHEN already warm THEN waitForWarm resolves immediately", async () => {
    const svc = StartupStateService.instance();
    svc.setState(ENGINE_STATE.WARM);
    await expect(svc.waitForWarm(50)).resolves.toBeUndefined();
  });

  test("WHEN waiting cold THEN waitForWarm resolves once state becomes warm", async () => {
    const svc = StartupStateService.instance();
    const pending = svc.waitForWarm(5_000);
    svc.setState(ENGINE_STATE.READY);
    await expect(pending).resolves.toBeUndefined();
  });

  test("WHEN the engine never warms THEN waitForWarm rejects after the timeout", async () => {
    const svc = StartupStateService.instance();
    await expect(svc.waitForWarm(25)).rejects.toThrow(/Timed out/);
  });

  test("WHEN cancelled THEN cancelled flag is set (deactivation guard)", () => {
    const svc = StartupStateService.instance();
    svc.cancel();
    expect(svc.cancelled).toBe(true);
  });

  test("WHEN reset THEN a fresh cold instance is returned", () => {
    const svc = StartupStateService.instance();
    svc.setState(ENGINE_STATE.WARM);
    StartupStateService.reset();
    const fresh = StartupStateService.instance();
    expect(fresh).not.toBe(svc);
    expect(fresh.state).toEqual(ENGINE_STATE.COLD);
  });
});
