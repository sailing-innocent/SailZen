import { APIUtils, ConfigUtils, SailAPI, SailError, ENGINE_STATE, ERROR_SEVERITY, EventEmitter, FuseEngine, NoteDictsUtils, NoteFnameDictUtils, NoteUtils, VaultUtils, } from "@saili/common-all";
import { createLogger, DConfig } from "@saili/common-server";
import fs from "fs-extra";
import _ from "lodash";
import { SQLiteMetadataStore, } from "./drivers/SQLiteMetadataStore";
import { EngineUtils } from "./utils";
export class SailEngineClient {
    _onNoteChangedEmitter = new EventEmitter();
    _config;
    /**
     * Last known engine state, based on init responses and status polls.
     * Responses from older servers that don't report a state are treated as
     * ready (full init semantics).
     */
    _engineState = ENGINE_STATE.COLD;
    notes;
    noteFnames;
    wsRoot;
    ws;
    fuseEngine;
    api;
    vaults;
    history;
    logger;
    hooks;
    static create({ port, vaults, ws, history, logger, }) {
        const api = new SailAPI({
            endpoint: APIUtils.getLocalEndpoint(_.isString(port) ? parseInt(port, 10) : port),
            apiPath: "api",
            logger,
        });
        return new SailEngineClient({ api, vaults, ws, history });
    }
    static getPort({ wsRoot }) {
        const portFile = EngineUtils.getPortFilePathForWorkspace({ wsRoot });
        if (!fs.pathExistsSync(portFile)) {
            throw new SailError({ message: "no port file" });
        }
        return _.toInteger(_.trim(fs.readFileSync(portFile, { encoding: "utf8" })));
    }
    constructor({ api, vaults, ws, history, logger, }) {
        this.api = api;
        this.notes = {};
        this.noteFnames = {};
        this.vaults = vaults;
        this.wsRoot = ws;
        this.ws = ws;
        this.history = history;
        this.logger = logger || createLogger();
        const config = DConfig.readConfigSync(ws);
        this.fuseEngine = new FuseEngine({
            fuzzThreshold: ConfigUtils.getLookup(config).note.fuzzThreshold,
        });
        this.hooks = ConfigUtils.getWorkspace(config).hooks || {
            onCreate: [],
        };
        this._config = config;
    }
    /**
     * Event that fires upon the changing of note state in the engine after a set
     * of NoteProps has been changed AND those changes have been reflected on the
     * engine side. Note creation, deletion, and updates are all fired from this
     * event.
     */
    get onEngineNoteStateChanged() {
        return this._onNoteChangedEmitter.event;
    }
    dispose() {
        this._onNoteChangedEmitter.dispose();
    }
    /** Last known engine lifecycle state reported by the server. */
    getEngineState() {
        return this._engineState;
    }
    /**
     * Poll the server for the current engine init status. Used during
     * fast-first startup while the full index runs in the background.
     */
    async fetchInitStatus() {
        const resp = await this.api.workspaceInitStatus({ ws: this.ws });
        if (resp.error) {
            throw new SailError({
                message: "unable to fetch engine init status",
                payload: resp.error,
            });
        }
        if (!resp.data) {
            throw new SailError({ message: "no data" });
        }
        this._engineState = resp.data.state;
        return resp.data;
    }
    /**
     * Load all nodes
     */
    async init(opts) {
        const resp = await this.api.workspaceInit({
            uri: this.ws,
            config: { vaults: this.vaults },
            mode: opts?.mode,
            priorityPaths: opts?.priorityPaths,
        });
        if (resp.error && resp.error.severity !== ERROR_SEVERITY.MINOR) {
            return {
                data: resp.data,
                error: resp.error,
            };
        }
        if (!resp.data) {
            throw new SailError({ message: "no data" });
        }
        const { notes, config } = resp.data;
        this._config = config;
        this._engineState = resp.data.engineState ?? ENGINE_STATE.READY;
        // Fire synthetic create entries for notes that were not part of the
        // previous snapshot. This drives incremental UI refresh (tree view,
        // lookup, backlinks) when a background full index replaces the warm
        // snapshot.
        const newEntries = _.values(notes)
            .filter((note) => _.isUndefined(this.notes[note.id]))
            .map((note) => ({ status: "create", note }));
        this.notes = notes;
        this.noteFnames = NoteFnameDictUtils.createNotePropsByFnameDict(this.notes);
        await this.fuseEngine.replaceNotesIndex(notes);
        if (newEntries.length > 0) {
            this._onNoteChangedEmitter.fire(newEntries);
        }
        return {
            error: resp.error,
            data: {
                notes,
                config,
                wsRoot: this.wsRoot,
                vaults: this.vaults,
                engineState: this._engineState,
            },
        };
    }
    /**
     * See {@link DStore.getNote}
     */
    async getNote(id) {
        return this.api.noteGet({ id, ws: this.ws });
    }
    async getNoteMeta(id) {
        const maybeNote = this.notes[id];
        if (maybeNote) {
            const noteMeta = _.omit(maybeNote, ["body"]);
            return { data: _.cloneDeep(noteMeta) };
        }
        return this.api.noteGetMeta({ id, ws: this.ws });
    }
    async bulkGetNotes(ids) {
        return this.api.noteBulkGet({ ids, ws: this.ws });
    }
    async bulkGetNotesMeta(ids) {
        const results = [];
        const missing = [];
        for (const id of ids) {
            const maybeNote = this.notes[id];
            if (maybeNote) {
                results.push(_.cloneDeep(_.omit(maybeNote, ["body"])));
            }
            else {
                missing.push(id);
            }
        }
        if (missing.length === 0) {
            return { data: results };
        }
        const apiResp = await this.api.noteBulkGetMeta({ ids: missing, ws: this.ws });
        return {
            error: apiResp.error,
            data: [...results, ...(apiResp.data ?? [])],
        };
    }
    /**
     * See {@link DStore.findNotes}
     */
    async findNotes(opts) {
        const resp = await this.api.noteFind({ ...opts, ws: this.ws });
        return resp.data;
    }
    /**
     * See {@link DStore.findNotesMeta}
     */
    async findNotesMeta(opts) {
        const { fname, vault, excludeStub } = opts;
        if (fname !== undefined && Object.keys(this.notes).length > 0) {
            const cleanedFname = fname.toLowerCase();
            const candidates = (this.noteFnames[cleanedFname] ?? [])
                .map((id) => this.notes[id])
                .filter(Boolean);
            let results = candidates.map((n) => _.cloneDeep(_.omit(n, ["body"])));
            if (vault) {
                results = results.filter((n) => VaultUtils.isEqual(vault, n.vault, this.wsRoot));
            }
            if (excludeStub) {
                results = results.filter((n) => !n.stub);
            }
            return results;
        }
        const resp = await this.api.noteFindMeta({ ...opts, ws: this.ws });
        return resp.data;
    }
    async bulkWriteNotes(opts) {
        const resp = await this.api.engineBulkAdd({ opts, ws: this.ws });
        const changed = resp.data;
        if (changed) {
            await this.refreshNotesV2(changed);
            this._onNoteChangedEmitter.fire(changed);
        }
        return resp;
    }
    async deleteNote(id, opts) {
        const ws = this.ws;
        const resp = await this.api.engineDelete({ id, opts, ws });
        if (!resp.data) {
            throw new SailError({
                message: `Failed to delete note with id ${id}`,
                payload: resp.error,
            });
        }
        await this.refreshNotesV2(resp.data);
        if (resp.data !== undefined) {
            this._onNoteChangedEmitter.fire(resp.data);
        }
        return {
            data: resp.data,
        };
    }
    async deleteSchema(id, opts) {
        const ws = this.ws;
        const resp = await this.api.schemaDelete({ id, opts, ws });
        if (!resp?.data?.notes) {
            throw new SailError({ message: "bad delete operation" });
        }
        const { notes } = resp.data;
        this.notes = notes;
        this.noteFnames = NoteFnameDictUtils.createNotePropsByFnameDict(this.notes);
        this.fuseEngine.replaceNotesIndex(notes);
        return {
            data: resp.data,
        };
    }
    async info() {
        const resp = await this.api.engineInfo();
        return resp;
    }
    async queryNotes(opts) {
        const { qs, onlyDirectChildren, vault, originalQS } = opts;
        let noteIndexProps;
        const config = DConfig.readConfigSync(this.wsRoot);
        if (config.workspace.metadataStore === "sqlite") {
            try {
                const resp = await SQLiteMetadataStore.search(qs);
                noteIndexProps = resp.hits;
                this.logger.debug({ ctx: "queryNote", query: resp.query });
            }
            catch (err) {
                fs.appendFileSync("/tmp/out.log", "ERROR: unable to query note", {
                    encoding: "utf8",
                });
                noteIndexProps = [];
            }
        }
        else {
            noteIndexProps = await this.fuseEngine.queryNote({
                qs,
                onlyDirectChildren,
                originalQS,
            });
        }
        let noteProps = noteIndexProps.map((ent) => this.notes[ent.id]);
        // TODO: hack
        if (!_.isUndefined(vault)) {
            noteProps = noteProps.filter((ent) => VaultUtils.isEqual(vault, ent.vault, this.wsRoot));
        }
        return noteProps;
    }
    async renderNote(opts) {
        return this.api.noteRender({ ...opts, ws: this.ws });
    }
    async refreshNotesV2(notes) {
        if (_.isUndefined(notes)) {
            return;
        }
        const noteDicts = {
            notesById: this.notes,
            notesByFname: this.noteFnames,
        };
        notes.forEach((ent) => {
            const uri = NoteUtils.getURI({ note: ent.note, wsRoot: this.wsRoot });
            if (ent.status === "delete") {
                NoteDictsUtils.delete(ent.note, noteDicts);
                this.history?.add({ source: "engine", action: "delete", uri });
            }
            else {
                if (ent.status === "create") {
                    this.history?.add({ source: "engine", action: "create", uri });
                }
                if (ent.status === "update") {
                    // If the note id has changed, delete previous entry from dict before adding
                    if (ent.prevNote && ent.prevNote.id !== ent.note.id) {
                        NoteDictsUtils.delete(ent.prevNote, noteDicts);
                    }
                    ent.note.children = _.sortBy(ent.note.children, (id) => _.get(this.notes, id, _.find(notes, (ent) => ent.note.id === id)?.note || {
                        title: "foo",
                    }).title);
                }
                NoteDictsUtils.add(ent.note, noteDicts);
            }
        });
        this.fuseEngine.replaceNotesIndex(this.notes);
    }
    /** Renames the note.
     *
     *  WARNING: When doing bulk operations. Do not invoke multiple requests to this
     *  command in parallel, wait for a single call to finish before requesting another call.
     *  Otherwise some race condition starts to cause intermittent failures.
     *  */
    async renameNote(opts) {
        const resp = await this.api.engineRenameNote({ ...opts, ws: this.ws });
        if (resp.error || _.isUndefined(resp.data)) {
            throw resp.error;
        }
        await this.refreshNotesV2(resp.data);
        if (resp.data) {
            this._onNoteChangedEmitter.fire(resp.data);
        }
        return resp;
    }
    async sync() {
        const resp = await this.api.workspaceSync({ ws: this.ws });
        if (!resp.data) {
            throw new SailError({ message: "no data", payload: resp });
        }
        const { notes, config } = resp.data;
        this.notes = notes;
        this.noteFnames = NoteFnameDictUtils.createNotePropsByFnameDict(this.notes);
        await this.fuseEngine.replaceNotesIndex(notes);
        return {
            error: resp.error,
            data: {
                notes,
                vaults: this.vaults,
                wsRoot: this.wsRoot,
                config,
            },
        };
    }
    async writeNote(note, opts) {
        const resp = await this.api.engineWrite({
            node: note,
            opts,
            ws: this.ws,
        });
        const changed = resp.data;
        if (resp.error) {
            return resp;
        }
        if (changed) {
            await this.refreshNotesV2(changed);
            this._onNoteChangedEmitter.fire(changed);
        }
        return resp;
    }
    // ~~~ schemas
    async getSchema(id) {
        return this.api.schemaRead({ id, ws: this.ws });
    }
    async querySchema(qs) {
        const out = await this.api.schemaQuery({ qs, ws: this.ws });
        return _.defaults(out, { data: [] });
    }
    async writeSchema(schema, opts) {
        this.logger.debug({
            ctx: "engineClient.writeSchema",
            schema: schema.fname,
            metaOnly: opts?.metaOnly,
        });
        return this.api.schemaWrite({ schema, ws: this.ws, opts });
    }
    async getNoteBlocks({ id, filterByAnchorType, }) {
        const out = await this.api.getNoteBlocks({
            id,
            filterByAnchorType,
            ws: this.ws,
        });
        return out;
    }
    async getDecorations(opts) {
        const out = await this.api.getDecorations({
            ...opts,
            ws: this.ws,
        });
        return out;
    }
}
//# sourceMappingURL=engineClient.js.map