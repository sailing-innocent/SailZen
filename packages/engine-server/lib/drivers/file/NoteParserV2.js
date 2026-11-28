import { SailError, DNodeUtils, DuplicateNoteError, ErrorFactory, ErrorUtils, ERROR_SEVERITY, ERROR_STATUS, NoteDictsUtils, NoteUtils, stringifyError, genHash, SchemaUtils, string2Note, globMatch, } from "@saili/common-all";
import { DConfig, vault2Path } from "@saili/common-server";
import fs from "fs-extra";
import _ from "lodash";
import path from "path";
import { createCacheEntry, EngineUtils } from "../../utils";
/**
 * Get hierarchy of each file
 * @param fpaths
 * @returns
 */
function getFileMeta(fpaths) {
    const metaDict = {};
    _.forEach(fpaths, (fpath) => {
        const { name } = path.parse(fpath);
        const lvl = name.split(".").length;
        if (!_.has(metaDict, lvl)) {
            metaDict[lvl] = [];
        }
        metaDict[lvl].push({ fpath });
    });
    return metaDict;
}
export class NoteParserV2 {
    opts;
    cache;
    engine;
    constructor(opts) {
        this.opts = opts;
        this.cache = opts.cache;
        this.engine = opts.engine;
    }
    get logger() {
        return this.opts.logger;
    }
    /**
     * Construct in-memory
     *
     * @param allPaths
     * @param vault
     * @returns
     */
    async parseFiles(allPaths, vault, schemas) {
        const ctx = "parseFiles";
        const fileMetaDict = getFileMeta(allPaths);
        const maxLvl = _.max(_.keys(fileMetaDict).map((e) => _.toInteger(e))) || 2;
        // In-memory representation of NoteProps dictionary
        const notesByFname = {};
        const notesById = {};
        const noteDicts = {
            notesById,
            notesByFname,
        };
        this.logger.info({ ctx, msg: "enter", vault });
        // Keep track of which notes in cache no longer exist
        const unseenKeys = this.cache.getCacheEntryKeys();
        const config = DConfig.readConfigSync(this.engine.wsRoot);
        const errors = [];
        // get root note
        if (_.isUndefined(fileMetaDict[1])) {
            return {
                noteDicts,
                errors: [
                    SailError.createFromStatus({
                        status: ERROR_STATUS.NO_ROOT_NOTE_FOUND,
                    }),
                ],
            };
        }
        const rootFile = fileMetaDict[1].find((n) => n.fpath === "root.md");
        if (!rootFile) {
            return {
                noteDicts,
                errors: [
                    SailError.createFromStatus({
                        status: ERROR_STATUS.NO_ROOT_NOTE_FOUND,
                    }),
                ],
            };
        }
        const rootProps = await this.parseNoteProps({
            fpath: rootFile.fpath,
            addParent: false,
            vault,
            config,
        });
        if (rootProps.error) {
            errors.push(rootProps.error);
        }
        if (!rootProps.data || rootProps.data.length === 0) {
            return {
                noteDicts,
                errors: [
                    SailError.createFromStatus({
                        status: ERROR_STATUS.NO_ROOT_NOTE_FOUND,
                    }),
                ],
            };
        }
        const rootNote = rootProps.data[0].note;
        NoteDictsUtils.add(rootNote, noteDicts);
        unseenKeys.delete(rootNote.fname);
        this.logger.info({ ctx, msg: "post:parseRootNote" });
        // Parse root hierarchies concurrently (addParent: false means no inter-note deps)
        const domainFiles = fileMetaDict[1].filter((n) => n.fpath !== "root.md");
        const domainResults = await Promise.all(domainFiles.map(async (ent) => {
            try {
                const resp = await this.parseNoteProps({
                    fpath: ent.fpath,
                    addParent: false,
                    vault,
                    config,
                });
                return { ent, resp, error: null };
            }
            catch (err) {
                return { ent, resp: null, error: err };
            }
        }));
        // Commit domain results to noteDicts serially (safe dict mutation)
        for (const { ent, resp, error: catchErr } of domainResults) {
            if (catchErr) {
                const error = ErrorFactory.wrapIfNeeded(catchErr);
                error.severity = ERROR_SEVERITY.MINOR;
                error.message =
                    `Failed to read ${ent.fpath} in ${vault.fsPath}: ` + error.message;
                errors.push(error);
                continue;
            }
            if (resp.error) {
                errors.push(resp.error);
            }
            if (resp.data && resp.data.length > 0) {
                const parsedNote = resp.data[0].note;
                unseenKeys.delete(parsedNote.fname);
                DNodeUtils.addChild(rootNote, parsedNote);
                if (notesById[parsedNote.id] !== undefined) {
                    const duplicate = notesById[parsedNote.id];
                    errors.push(new DuplicateNoteError({ noteA: duplicate, noteB: parsedNote }));
                }
                NoteDictsUtils.add(parsedNote, noteDicts);
            }
        }
        this.logger.info({ ctx, msg: "post:parseDomainNotes" });
        // Parse level by level (levels must be sequential: child needs parent in noteDicts).
        // Within each level:
        //   Phase 1 (concurrent): read files from disk and parse note props (pure IO, no shared-state mutation)
        //   Phase 2 (serial):     call addOrUpdateParents so parent/child links are built without races
        let lvl = 2;
        while (lvl <= maxLvl) {
            const lvlFiles = (fileMetaDict[lvl] || []).filter((ent) => !globMatch(["root.*"], ent.fpath));
            // Phase 1: concurrent file IO - parse each note WITHOUT touching noteDicts
            const ioResults = await Promise.all(lvlFiles.map(async (ent) => {
                try {
                    const resp = await this.parseNoteProps({
                        fpath: ent.fpath,
                        addParent: false,
                        vault,
                        config,
                    });
                    return { ent, resp, error: null };
                }
                catch (err) {
                    return { ent, resp: null, error: err };
                }
            }));
            // Phase 2: serial parent linking - addOrUpdateParents mutates noteDicts so must be sequential
            for (const { ent, resp, error: catchErr } of ioResults) {
                if (catchErr) {
                    const sailError = ErrorFactory.wrapIfNeeded(catchErr);
                    sailError.severity = ERROR_SEVERITY.MINOR;
                    sailError.message =
                        `Failed to read ${ent.fpath} in ${vault.fsPath}: ` +
                            sailError.message;
                    errors.push(sailError);
                    continue;
                }
                if (resp.error) {
                    errors.push(resp.error);
                }
                if (resp.data && resp.data.length > 0) {
                    const parsedNote = resp.data[0].note;
                    unseenKeys.delete(parsedNote.fname);
                    const changed = NoteUtils.addOrUpdateParents({
                        note: parsedNote,
                        noteDicts,
                        createStubs: true,
                    });
                    if (notesById[parsedNote.id] !== undefined) {
                        errors.push(new DuplicateNoteError({
                            noteA: notesById[parsedNote.id],
                            noteB: parsedNote,
                        }));
                    }
                    NoteDictsUtils.add(parsedNote, noteDicts);
                    // Must write back both "create" and "update" entries:
                    // addOrUpdateParents operates on cloneDeep copies from findByFname
                    changed.forEach((entry) => {
                        if (entry.note.id !== parsedNote.id) {
                            NoteDictsUtils.add(entry.note, noteDicts);
                        }
                    });
                }
            }
            lvl += 1;
        }
        this.logger.info({ ctx, msg: "post:parseAllNotes" });
        // Add schemas
        const domains = notesById[rootNote.id].children.map((ent) => notesById[ent]);
        domains.map((domain) => {
            SchemaUtils.matchDomain(domain, notesById, schemas);
        });
        // Remove stale entries from cache
        unseenKeys.forEach((unseenKey) => {
            this.cache.drop(unseenKey);
        });
        // OPT:make async and don't wait for return
        // Skip this if we found no notes, which means vault did not initialize, or if there are no cache changes needed
        if ((_.size(notesById) > 0 && this.cache.numCacheMisses > 0) ||
            unseenKeys.size > 0) {
            this.cache.writeToFileSystem();
        }
        this.logger.info({ ctx, msg: "post:matchSchemas" });
        return {
            noteDicts,
            errors,
        };
    }
    /**
     * Given a fpath, convert to NoteProp
     * Update parent/children metadata if parents = true
     *
     * @returns List of all notes changed. If a note has no direct parents, stub notes are added instead
     */
    async parseNoteProps(opts) {
        const cleanOpts = _.defaults(opts, {
            addParent: true,
            noteDicts: {
                notesById: {},
                notesByFname: {},
            },
        });
        const { fpath, noteDicts, vault, config } = cleanOpts;
        const ctx = "parseNoteProps";
        this.logger.debug({ ctx, msg: "enter", fpath });
        const wsRoot = this.engine.wsRoot;
        const vpath = vault2Path({ vault, wsRoot });
        let changeEntries = [];
        try {
            // Get note props from file and propagate any errors
            const { data: note, error } = await this.file2NoteWithCache({
                fpath: path.join(vpath, fpath),
                vault,
                config,
            });
            if (note) {
                changeEntries.push({ status: "create", note });
                // Add parent/children properties
                if (cleanOpts.addParent) {
                    const changed = NoteUtils.addOrUpdateParents({
                        note,
                        noteDicts,
                        createStubs: true,
                    });
                    changeEntries = changeEntries.concat(changed);
                }
            }
            return { data: changeEntries, error };
        }
        catch (_err) {
            if (!ErrorUtils.isSailError(_err)) {
                const error = SailError.createFromStatus({
                    status: ERROR_STATUS.BAD_PARSE_FOR_NOTE,
                    severity: ERROR_SEVERITY.MINOR,
                    payload: { fname: fpath, error: stringifyError(_err) },
                    message: `${fpath} could not be parsed`,
                });
                this.logger.error({ ctx, error });
                return { error };
            }
            return { error: _err };
        }
    }
    /**
     * Given a fpath, attempt to convert raw file contents into a NoteProp
     *
     * Look up metadata from cache. If contenthash hasn't changed, use metadata from cache.
     * Otherwise, reconstruct metadata from scratch
     *
     * @returns NoteProp associated with fpath
     */
    async file2NoteWithCache({ fpath, vault, config, }) {
        const content = fs.readFileSync(fpath, { encoding: "utf8" });
        const { name } = path.parse(fpath);
        const sig = genHash(content);
        const cacheEntry = this.cache.get(name);
        const matchHash = cacheEntry?.hash === sig;
        let note;
        // if hash matches, note hasn't changed
        if (matchHash) {
            // since we don't store the note body in the cache file, we need to re-parse the body
            const capture = content.match(/^---[\s\S]+?---/);
            if (capture) {
                const offset = capture[0].length;
                const body = content.slice(offset + 1);
                // vault can change without note changing so we need to add this
                // add `contentHash` to this signature because its not saved with note
                note = {
                    ...cacheEntry.data,
                    body,
                    vault,
                    contentHash: sig,
                    children: [],
                    parent: null,
                };
                return { data: note, error: null };
            }
            else {
                // No frontmatter exists for this file, return error
                return {
                    error: new SailError({
                        message: `File "${fpath}" is missing frontmatter.`,
                        severity: ERROR_SEVERITY.MINOR,
                    }),
                };
            }
        }
        // If hash is different, then we update all links and anchors ^link-anchor
        note = string2Note({ content, fname: name, vault });
        note.contentHash = sig;
        // Link/anchor errors should be logged but not interfere with rest of parsing
        let error = null;
        try {
            await EngineUtils.refreshNoteLinksAndAnchors({
                note,
                engine: this.engine,
                config,
            });
        }
        catch (_err) {
            error = ErrorFactory.wrapIfNeeded(_err);
        }
        // Update cache entry as well
        this.cache.set(name, createCacheEntry({
            noteProps: note,
            hash: note.contentHash,
        }));
        this.cache.incrementCacheMiss();
        return { data: note, error };
    }
}
//# sourceMappingURL=NoteParserV2.js.map