/**
 * Tests for the fast-first startup server behavior of WorkspaceController:
 * - minimal init passthrough (mode/priorityPaths) + warm engine state
 * - full init reusing the warm engine (no state loss, no second engine)
 * - legacy init without mode performs a full init
 * - initQueue serialization of concurrent inits on the same workspace
 * - /initStatus reporting (cold/warm/ready)
 * - a failed init does not poison the per-workspace init queue
 */
import { Time } from "@saili/common-all";
import fs from "fs-extra";
import os from "os";
import path from "path";
import { WorkspaceController } from "../modules/workspace";
import { getWSEngine } from "../utils";

function noteContent(opts: { id: string; title: string; body?: string }) {
  return [
    "---",
    `id: ${opts.id}`,
    `title: ${opts.title}`,
    'desc: ""',
    "updated: 1608143370884",
    "created: 1608143370884",
    "---",
    "",
    opts.body ?? `Body of ${opts.title}`,
    "",
  ].join("\n");
}

const JOURNAL_SCHEMA = [
  "version: 1",
  "schemas:",
  "  - id: journal",
  "    parent: root",
  "    children:",
  "      - pattern: daily",
  "        children:",
  "          - pattern: '[0-2][0-9][0-9][0-9]'",
  "            children:",
  "              - pattern: '[0-1][0-9]'",
  "                children:",
  "                  - pattern: '[0-3][0-9]'",
  "                    template:",
  "                      id: templates.daily",
  "                      type: note",
  "",
].join("\n");

/**
 * Create a temporary workspace with a single vault and a handful of notes.
 */
async function setupWorkspace(opts: { withTodayNote: boolean }) {
  const wsRoot = await fs.mkdtemp(path.join(os.tmpdir(), "sail-api-test-"));
  const vaultPath = path.join(wsRoot, "vault");
  await fs.ensureDir(vaultPath);
  await fs.writeFile(
    path.join(wsRoot, "sail.yml"),
    [
      "version: 5",
      "workspace:",
      "  vaults:",
      "    - fsPath: vault",
      "  journal:",
      "    dailyDomain: daily",
      "    name: journal",
      "    dateFormat: y.MM.dd",
      "    addBehavior: childOfCurrent",
      "",
    ].join("\n")
  );
  await fs.writeFile(
    path.join(vaultPath, "journal.schema.yml"),
    JOURNAL_SCHEMA
  );
  const todayFname = `journal.daily.${Time.now().toFormat("y.MM.dd")}`;
  const notes: Record<string, string> = {
    "root.md": noteContent({ id: "root-id", title: "root" }),
    "journal.md": noteContent({ id: "journal-id", title: "journal" }),
    "templates.daily.md": noteContent({
      id: "template-id",
      title: "Daily template",
      body: "Template body",
    }),
    "foo.md": noteContent({ id: "foo-id", title: "Foo" }),
    "foo.one.md": noteContent({ id: "foo-one-id", title: "Foo One" }),
    "alpha.md": noteContent({ id: "alpha-id", title: "Alpha" }),
  };
  if (opts.withTodayNote) {
    notes[`${todayFname}.md`] = noteContent({
      id: "today-id",
      title: "Today",
      body: "Today body",
    });
  }
  for (const [fname, content] of Object.entries(notes)) {
    await fs.writeFile(path.join(vaultPath, fname), content);
  }
  return { wsRoot, vaultPath, todayFname };
}

async function settled(p: Promise<unknown>) {
  try {
    return { ok: true as const, value: await p };
  } catch (err) {
    return { ok: false as const, err };
  }
}

describe("GIVEN WorkspaceController fast-first startup", () => {
  // NOTE: WorkspaceController is a process-wide singleton. Every test uses a
  // unique wsRoot (fs.mkdtemp) so per-workspace state never leaks between
  // tests.

  test("WHEN initStatus is queried for an unknown workspace THEN state is cold", async () => {
    const ctl = WorkspaceController.instance();
    const resp = await ctl.initStatus({
      ws: path.join(os.tmpdir(), "sail-api-does-not-exist"),
    });
    expect(resp.error).toBeUndefined();
    expect(resp.data.state).toEqual("cold");
  });

  test("WHEN minimal init THEN engine is created, priority notes parsed (stubs excluded), state warm", async () => {
    const { wsRoot, todayFname } = await setupWorkspace({
      withTodayNote: true,
    });
    const ctl = WorkspaceController.instance();
    const resp = await ctl.init({
      uri: wsRoot,
      mode: "minimal",
      priorityPaths: [todayFname, "templates.daily"],
    });
    expect(resp.error).toBeFalsy();
    const notes = resp.data!.notes!;
    // priority notes are fully parsed
    expect(Object.keys(notes)).toContain("today-id");
    expect(Object.keys(notes)).toContain("template-id");
    // non-priority notes exist only as server-side stubs and must NOT be in
    // the client payload
    expect(Object.keys(notes)).not.toContain("foo-id");
    expect(Object.keys(notes)).not.toContain("foo-one-id");

    const status = await ctl.initStatus({ ws: wsRoot });
    expect(status.data.state).toEqual("warm");
  });

  test("WHEN full init follows minimal init THEN the warm engine is reused and state becomes ready", async () => {
    const { wsRoot, todayFname } = await setupWorkspace({
      withTodayNote: true,
    });
    const ctl = WorkspaceController.instance();
    await ctl.init({
      uri: wsRoot,
      mode: "minimal",
      priorityPaths: [todayFname],
    });
    const engineBefore = await getWSEngine({ ws: wsRoot });

    const fullResp = await ctl.init({ uri: wsRoot, mode: "full" });

    const engineAfter = await getWSEngine({ ws: wsRoot });
    // engine reuse: creating a new engine here would discard warm state and
    // any notes written while warm
    expect(engineAfter).toBe(engineBefore);
    expect(fullResp.error).toBeFalsy();
    const notes = fullResp.data!.notes!;
    // full parse now includes everything (stubs resolved to full notes)
    expect(Object.keys(notes)).toContain("foo-id");
    expect(Object.keys(notes)).toContain("today-id");

    const status = await ctl.initStatus({ ws: wsRoot });
    expect(status.data.state).toEqual("ready");
    expect(status.data.progress).toBeUndefined();
  });

  test("WHEN init is called without a mode THEN a legacy full init runs", async () => {
    const { wsRoot } = await setupWorkspace({ withTodayNote: false });
    const ctl = WorkspaceController.instance();
    const resp = await ctl.init({ uri: wsRoot });
    expect(resp.error).toBeFalsy();
    expect(Object.keys(resp.data!.notes!)).toContain("foo-id");
    const status = await ctl.initStatus({ ws: wsRoot });
    expect(status.data.state).toEqual("ready");
  });

  test("WHEN minimal and full inits run concurrently on one workspace THEN they are serialized", async () => {
    const { wsRoot, todayFname } = await setupWorkspace({
      withTodayNote: true,
    });
    const ctl = WorkspaceController.instance();
    const pMinimal = ctl.init({
      uri: wsRoot,
      mode: "minimal",
      priorityPaths: [todayFname],
    });
    const pFull = ctl.init({ uri: wsRoot, mode: "full" });
    const [rMinimal, rFull] = await Promise.all([pMinimal, pFull]);

    // Serialization guarantees the minimal response was computed before the
    // full init ran, so it carries the warm payload (priority note present,
    // non-priority notes still stub-only).
    expect(rMinimal.error).toBeFalsy();
    expect(Object.keys(rMinimal.data!.notes!)).toContain("today-id");
    expect(Object.keys(rMinimal.data!.notes!)).not.toContain("foo-id");

    // The full response carries the complete note set.
    expect(rFull.error).toBeFalsy();
    expect(Object.keys(rFull.data!.notes!)).toContain("foo-id");

    const status = await ctl.initStatus({ ws: wsRoot });
    expect(status.data.state).toEqual("ready");
  });

  test("WHEN an init fails THEN the per-workspace queue tail stays rejection-free", async () => {
    // A workspace root without sail.yml makes the engine init fail.
    const badRoot = await fs.mkdtemp(path.join(os.tmpdir(), "sail-api-bad-"));
    const ctl = WorkspaceController.instance();

    const first = await settled(
      ctl.init({ uri: badRoot, mode: "minimal" })
    );

    // The stored queue tail must not be rejected - otherwise every
    // subsequent init on this workspace would reject with the original
    // failure (poisoned queue).
    const tail: Promise<unknown> | undefined = (ctl as any)._initQueues.get(
      badRoot.toLowerCase()
    );
    expect(tail).toBeDefined();
    await expect(tail).resolves.toBeUndefined();

    // A second init on the same workspace still settles (does not hang and
    // is not swallowed by the first failure).
    const second = await settled(
      ctl.init({ uri: badRoot, mode: "minimal" })
    );
    expect(first.ok).toBeDefined();
    expect(second.ok).toBeDefined();
  });
});
