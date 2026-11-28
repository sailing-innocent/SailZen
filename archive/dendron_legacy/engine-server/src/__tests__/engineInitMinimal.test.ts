/**
 * Tests for the fast-first startup engine state machine:
 * - SailEngine.initMinimal (warm state: schemas + priority notes + stubs)
 * - writeNote during warm (new notes and stub promotion)
 * - full init after warm (ready state, stub cleanup, warm writes preserved)
 */
import { NotePropsMeta, NoteUtils, Time } from "@saili/common-all";
import fs from "fs-extra";
import os from "os";
import path from "path";
import { SailEngine } from "../SailEngine";

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
  '          - pattern: "[0-2][0-9][0-9][0-9]"',
  "            children:",
  '              - pattern: "[0-1][0-9]"',
  "                children:",
  '                  - pattern: "[0-3][0-9]"',
  "                    template:",
  "                      id: templates.daily",
  "                      type: note",
  "",
].join("\n");

/**
 * Create a temporary workspace with a single vault and a handful of notes.
 */
async function setupWorkspace(opts: { withTodayNote: boolean }) {
  const wsRoot = await fs.mkdtemp(path.join(os.tmpdir(), "sail-engine-test-"));
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
  await fs.writeFile(path.join(vaultPath, "journal.schema.yml"), JOURNAL_SCHEMA);

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
    "foo.two.md": noteContent({ id: "foo-two-id", title: "Foo Two" }),
    "alpha.md": noteContent({ id: "alpha-id", title: "Alpha" }),
    "alpha.beta.md": noteContent({
      id: "alpha-beta-id",
      title: "Alpha Beta",
      body: "Links to [[foo]] and [[foo.one]]",
    }),
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

describe("WHEN engine is initialized minimally", () => {
  let wsRoot: string;
  let vaultPath: string;
  let todayFname: string;
  let engine: SailEngine;
  let warmResp: Awaited<ReturnType<SailEngine["initMinimal"]>>;

  beforeAll(async () => {
    const setup = await setupWorkspace({ withTodayNote: true });
    wsRoot = setup.wsRoot;
    vaultPath = setup.vaultPath;
    todayFname = setup.todayFname;
    engine = SailEngine.create({ wsRoot });
    warmResp = await engine.initMinimal({
      priorityPaths: [todayFname, "templates.daily"],
    });
  });

  afterAll(async () => {
    await fs.remove(wsRoot);
  });

  test("THEN warm state is reached with priority notes parsed", () => {
    expect(warmResp.error).toBeUndefined();
    expect(warmResp.data.engineState).toEqual("warm");
    expect(engine.getEngineState()).toEqual("warm");

    const notes = Object.values(warmResp.data.notes);
    // priority notes fully parsed
    const today = notes.find((n) => n.fname === todayFname);
    expect(today).toBeDefined();
    expect(today!.stub).toBeFalsy();
    expect(today!.body).toContain("Today body");
    const template = notes.find((n) => n.fname === "templates.daily");
    expect(template).toBeDefined();
    expect(template!.body).toContain("Template body");
  });

  test("THEN non-priority notes are stubs not present in the payload", () => {
    const notes = Object.values(warmResp.data.notes);
    // root + journal + template + today fully parsed; no stubs leak into payload
    const stubNotes = notes.filter((n) => n.stub);
    expect(stubNotes).toEqual([]);
    expect(notes.find((n) => n.fname === "foo")).toBeUndefined();
  });

  test("THEN findNotesMeta resolves stub entries by fname", async () => {
    const metas: NotePropsMeta[] = await engine.findNotesMeta({
      fname: "foo",
    });
    expect(metas.length).toEqual(1);
    expect(metas[0].stub).toBe(true);
    expect(metas[0].fname).toEqual("foo");
  });

  test("THEN schema queries work", async () => {
    const resp = await engine.querySchema("journal");
    expect(resp.error).toBeUndefined();
    const schemas = resp.data!;
    expect(schemas.length).toBeGreaterThan(0);
    expect(schemas[0].root.id).toEqual("journal");
  });

  test("THEN writeNote of a new journal note works during warm", async () => {
    const newNote = NoteUtils.create({
      fname: "journal.daily.2099.01.01",
      vault: engine.vaults[0],
    });
    newNote.body = "future journal body";
    const resp = await engine.writeNote(newNote);
    expect(resp.error).toBeUndefined();
    // written to filesystem
    expect(
      await fs.pathExists(path.join(vaultPath, `${newNote.fname}.md`))
    ).toBe(true);
    // findable by fname
    const metas = await engine.findNotesMeta({ fname: newNote.fname });
    expect(metas.length).toEqual(1);
    expect(metas[0].id).toEqual(newNote.id);
    expect(metas[0].stub).toBeFalsy();
  });

  test("THEN writeNote over an existing stub promotes it", async () => {
    const metasBefore = await engine.findNotesMeta({ fname: "foo" });
    expect(metasBefore.length).toEqual(1);
    expect(metasBefore[0].stub).toBe(true);

    const note = NoteUtils.create({
      fname: "foo",
      vault: engine.vaults[0],
    });
    note.body = "foo full body";
    const resp = await engine.writeNote(note);
    expect(resp.error).toBeUndefined();

    const metasAfter = await engine.findNotesMeta({ fname: "foo" });
    expect(metasAfter.length).toEqual(1);
    expect(metasAfter[0].id).toEqual(note.id);
    expect(metasAfter[0].stub).toBeFalsy();
  });

  test("THEN full init reaches ready and preserves warm writes", async () => {
    const resp = await engine.init();
    expect(resp.error).toBeUndefined();
    expect(resp.data.engineState).toEqual("ready");
    expect(engine.getEngineState()).toEqual("ready");

    const notes = Object.values(resp.data.notes);
    const byFname = (fname: string) => notes.filter((n) => n.fname === fname);

    // every note on disk is now a full note
    expect(byFname("foo").length).toEqual(1);
    expect(byFname("foo")[0].stub).toBeFalsy();
    expect(byFname("foo")[0].body).toContain("foo full body");
    expect(byFname("alpha.beta").length).toEqual(1);
    expect(byFname("alpha.beta")[0].stub).toBeFalsy();
    // today's note survived the full index
    const today = byFname(todayFname);
    expect(today.length).toEqual(1);
    expect(today[0].body).toContain("Today body");
    // warm-period write is preserved (was written to disk during warm)
    expect(byFname("journal.daily.2099.01.01").length).toEqual(1);
    expect(byFname("journal.daily.2099.01.01")[0].body).toContain(
      "future journal body"
    );
    // no duplicate fname entries remain from stubs
    const fooMetas = await engine.findNotesMeta({ fname: "foo" });
    expect(fooMetas.length).toEqual(1);
  });

  test("THEN repeated full init stays ready", async () => {
    const resp = await engine.init();
    expect(resp.data.engineState).toEqual("ready");
    expect(engine.getEngineState()).toEqual("ready");
  });
});

describe("WHEN engine is initialized minimally without a today note", () => {
  let wsRoot: string;
  let todayFname: string;
  let engine: SailEngine;

  beforeAll(async () => {
    const setup = await setupWorkspace({ withTodayNote: false });
    wsRoot = setup.wsRoot;
    todayFname = setup.todayFname;
    engine = SailEngine.create({ wsRoot });
  });

  afterAll(async () => {
    await fs.remove(wsRoot);
  });

  test("THEN warm init succeeds and today's note can be created", async () => {
    const resp = await engine.initMinimal({
      priorityPaths: [todayFname, "templates.daily"],
    });
    // missing priority files are fine (today's note does not exist yet)
    expect(
      resp.error === undefined || resp.error?.severity === "minor"
    ).toBeTruthy();
    expect(engine.getEngineState()).toEqual("warm");

    // creating today's note during warm works
    const note = NoteUtils.create({
      fname: todayFname,
      vault: engine.vaults[0],
    });
    note.body = "created during warm";
    const writeResp = await engine.writeNote(note);
    expect(writeResp.error).toBeUndefined();
    // schema applied from the journal schema module
    expect(note.schema).toBeDefined();
    expect(note.schema!.moduleId).toEqual("journal");

    // and survives the full index
    const fullResp = await engine.init();
    const today = Object.values(fullResp.data.notes).find(
      (n) => n.fname === todayFname
    );
    expect(today).toBeDefined();
    expect(today!.body).toContain("created during warm");
  });
});
