import { asyncLoopOneAtATime, ConfigUtils, SailError, extractNoteChangeEntryCounts, genUUID, InvalidFilenameReason, isNotUndefined, NoteDictsUtils, NoteUtils, ProcFlavor, VaultUtils, } from "@saili/common-all";
import { createDisposableLogger, DConfig, isSelfContainedVaultFolder, pathForVaultRoot, } from "@saili/common-server";
import throttle from "@jcoreio/async-throttle";
import fs from "fs-extra";
import _ from "lodash";
import path from "path";
import { DEPRECATED_PATHS, Git, WorkspaceService } from "..";
import { ProcMode, MDUtilsV5, LinkUtils, RemarkUtils, SailASTDest, } from "@saili/unified";
export var DoctorActionsEnum;
(function (DoctorActionsEnum) {
    DoctorActionsEnum["FIX_FRONTMATTER"] = "fixFrontmatter";
    DoctorActionsEnum["H1_TO_TITLE"] = "h1ToTitle";
    DoctorActionsEnum["HI_TO_H2"] = "h1ToH2";
    DoctorActionsEnum["REMOVE_STUBS"] = "removeStubs";
    DoctorActionsEnum["CREATE_MISSING_LINKED_NOTES"] = "createMissingLinkedNotes";
    DoctorActionsEnum["REGENERATE_NOTE_ID"] = "regenerateNoteId";
    DoctorActionsEnum["FIND_BROKEN_LINKS"] = "findBrokenLinks";
    DoctorActionsEnum["FIX_REMOTE_VAULTS"] = "fixRemoteVaults";
    DoctorActionsEnum["ADD_MISSING_DEFAULT_CONFIGS"] = "addMissingDefaultConfigs";
    DoctorActionsEnum["REMOVE_DEPRECATED_CONFIGS"] = "removeDeprecatedConfigs";
    DoctorActionsEnum["FIX_SELF_CONTAINED_VAULT_CONFIG"] = "fixSelfContainedVaultsInConfig";
    DoctorActionsEnum["FIX_INVALID_FILENAMES"] = "fixInvalidFileNames";
})(DoctorActionsEnum || (DoctorActionsEnum = {}));
/** DoctorService is a disposable, you **must** dispose instances you create
 * otherwise you risk leaking file descriptors which may lead to crashes. */
export class DoctorService {
    L;
    loggerDispose;
    print;
    constructor(opts) {
        const { logger, dispose } = createDisposableLogger("DoctorService");
        this.L = logger;
        this.loggerDispose = dispose;
        // if given a print function, use that.
        // otherwise, no-op
        this.print = opts?.printFunc ? opts.printFunc : () => { };
    }
    dispose() {
        this.loggerDispose();
    }
    findBrokenLinks(note, noteDicts, engine) {
        const { vaults } = engine;
        const links = note.links;
        if (_.isEmpty(links)) {
            return [];
        }
        const out = _.filter(links, (link) => {
            if (link.type !== "wiki") {
                return false;
            }
            const hasVaultPrefix = LinkUtils.hasVaultPrefix(link);
            let vault;
            if (hasVaultPrefix) {
                vault = VaultUtils.getVaultByName({
                    vaults,
                    vname: link.to.vaultName,
                });
                if (!vault)
                    return false;
            }
            const isMultiVault = vaults.length > 1;
            const noteExists = NoteDictsUtils.findByFname({
                fname: link.to.fname,
                noteDicts,
                vault: hasVaultPrefix ? vault : note.vault,
            })[0];
            if (hasVaultPrefix) {
                // true: link w/ vault prefix that points to nothing. (candidate for sure)
                // false: link w/ vault prefix that points to a note. (valid link)
                return !noteExists;
            }
            if (!noteExists) {
                // true: no vault prefix and single vault. (candidate for sure)
                // false: no vault prefix and multi vault. (ambiguous)
                return !isMultiVault;
            }
            // (valid link)
            return false;
        });
        return out;
    }
    getBrokenLinkDestinations(notes, engine) {
        const { vaults } = engine;
        let brokenWikiLinks = [];
        const noteDicts = NoteDictsUtils.createNoteDicts(notes);
        _.forEach(notes, (note) => {
            const links = note.links;
            if (_.isEmpty(links)) {
                return;
            }
            const brokenLinks = this.findBrokenLinks(note, noteDicts, engine);
            brokenWikiLinks = brokenWikiLinks.concat(brokenLinks);
            return true;
        });
        const uniqueCandidates = _.map(_.uniqBy(brokenWikiLinks, "to.fname"), (link) => {
            const destVault = link.to?.vaultName
                ? VaultUtils.getVaultByName({ vaults, vname: link.to.vaultName })
                : VaultUtils.getVaultByName({ vaults, vname: link.from.vaultName });
            return NoteUtils.create({
                fname: link.to.fname,
                vault: destVault,
            });
        });
        return uniqueCandidates;
    }
    async findMisconfiguredSelfContainedVaults(wsRoot, vaults) {
        return (await Promise.all(vaults.map(async (vault) => {
            if (vault.selfContained || vault.workspace || vault.seed)
                return;
            if (await isSelfContainedVaultFolder(path.join(wsRoot, vault.fsPath))) {
                return vault;
            }
            return;
        }))).filter(isNotUndefined);
    }
    async executeDoctorActions(opts) {
        const { action, engine, query, candidates, limit, dryRun, exit, podId, hierarchy, vault, } = _.defaults(opts, {
            limit: 99999,
            exit: true,
        });
        let notes;
        if (_.isUndefined(candidates)) {
            notes =
                (query
                    ? await engine.queryNotes({ qs: query, originalQS: query })
                    : await engine.findNotes({ excludeStub: true })) ?? [];
        }
        else {
            notes = candidates;
        }
        if (notes) {
            notes = notes.filter((n) => !n.stub);
        }
        const noteDicts = NoteDictsUtils.createNoteDicts(notes);
        // this.L.info({ msg: "prep doctor", numResults: notes.length });
        let numChanges = 0;
        let resp;
        const engineWrite = dryRun
            ? () => { }
            : throttle(_.bind(engine.writeNote, engine), 300, {
                // @ts-ignore
                leading: true,
            });
        const engineDelete = dryRun
            ? () => { }
            : throttle(_.bind(engine.deleteNote, engine), 300, {
                // @ts-ignore
                leading: true,
            });
        let doctorAction;
        switch (action) {
            case DoctorActionsEnum.REMOVE_DEPRECATED_CONFIGS: {
                const { wsRoot } = engine;
                const rawConfig = DConfig.getRaw(wsRoot);
                const config = DConfig.readConfigSync(wsRoot);
                const pathsToDelete = ConfigUtils.detectDeprecatedConfigs({
                    config: rawConfig,
                    deprecatedPaths: DEPRECATED_PATHS,
                });
                if (pathsToDelete.length > 0) {
                    const backupPath = await this.createBackup(wsRoot, DoctorActionsEnum.REMOVE_DEPRECATED_CONFIGS);
                    if (backupPath instanceof SailError) {
                        return {
                            exit: true,
                            error: backupPath,
                        };
                    }
                    const configDeepCopy = _.cloneDeep(config);
                    pathsToDelete.forEach((path) => {
                        _.unset(configDeepCopy, path);
                    });
                    await DConfig.writeConfig({ wsRoot, config: configDeepCopy });
                    return {
                        exit: true,
                        resp: {
                            backupPath,
                        },
                    };
                }
                return { exit: true };
            }
            case DoctorActionsEnum.ADD_MISSING_DEFAULT_CONFIGS: {
                const { wsRoot } = engine;
                const rawConfig = DConfig.getRaw(wsRoot);
                const detectOut = ConfigUtils.detectMissingDefaults({
                    config: rawConfig,
                });
                if (detectOut) {
                    const { needsBackfill, backfilledConfig } = detectOut;
                    if (needsBackfill) {
                        // back up sail.yml first
                        const backupPath = await this.createBackup(wsRoot, DoctorActionsEnum.ADD_MISSING_DEFAULT_CONFIGS);
                        if (backupPath instanceof SailError) {
                            return {
                                exit: true,
                                error: backupPath,
                            };
                        }
                        // write config
                        await DConfig.writeConfig({ wsRoot, config: backfilledConfig });
                        return {
                            exit: true,
                            resp: {
                                backupPath,
                            },
                        };
                    }
                }
                return { exit: true };
            }
            case DoctorActionsEnum.FIX_FRONTMATTER: {
                this.print("the CLI currently doesn't support this action. please run this using the plugin");
                return { exit };
            }
            // eslint-disable-next-line no-fallthrough
            case DoctorActionsEnum.H1_TO_TITLE: {
                doctorAction = async (note) => {
                    const changes = [];
                    const proc = MDUtilsV5._procRemark({
                        mode: ProcMode.IMPORT,
                        flavor: ProcFlavor.REGULAR,
                    }, {
                        dest: SailASTDest.MD_SAIL,
                        noteToRender: note,
                        fname: note.fname,
                        vault: note.vault,
                        config: DConfig.readConfigSync(engine.wsRoot),
                    });
                    const newBody = await proc()
                        .use(RemarkUtils.h1ToTitle(note, changes))
                        .process(note.body);
                    note.body = newBody.toString();
                    if (!_.isEmpty(changes)) {
                        await engineWrite(note);
                        this.L.info({ msg: `changes ${note.fname}`, changes });
                        numChanges += 1;
                        return;
                    }
                    else {
                        return;
                    }
                };
                break;
            }
            case DoctorActionsEnum.HI_TO_H2: {
                doctorAction = async (note) => {
                    const changes = [];
                    const proc = MDUtilsV5._procRemark({
                        mode: ProcMode.IMPORT,
                        flavor: ProcFlavor.REGULAR,
                    }, {
                        dest: SailASTDest.MD_SAIL,
                        noteToRender: note,
                        fname: note.fname,
                        vault: note.vault,
                        config: DConfig.readConfigSync(engine.wsRoot),
                    });
                    const newBody = await proc()
                        .use(RemarkUtils.h1ToH2(note, changes))
                        .process(note.body);
                    note.body = newBody.toString();
                    if (!_.isEmpty(changes)) {
                        await engineWrite(note);
                        this.L.info({ msg: `changes ${note.fname}`, changes });
                        numChanges += 1;
                        return;
                    }
                    else {
                        return;
                    }
                };
                break;
            }
            case DoctorActionsEnum.REMOVE_STUBS: {
                doctorAction = async (note) => {
                    const changes = [];
                    if (_.trim(note.body) === "") {
                        changes.push({
                            status: "delete",
                            note,
                        });
                    }
                    if (!_.isEmpty(changes)) {
                        await engineDelete(note.id);
                        const vname = VaultUtils.getName(note.vault);
                        this.L.info(`doctor ${DoctorActionsEnum.REMOVE_STUBS} ${note.fname} ${vname}`);
                        numChanges += 1;
                        return;
                    }
                    else {
                        return;
                    }
                };
                break;
            }
            case DoctorActionsEnum.CREATE_MISSING_LINKED_NOTES: {
                notes = this.getBrokenLinkDestinations(notes, engine);
                doctorAction = async (note) => {
                    await engineWrite(note);
                    numChanges += 1;
                };
                break;
            }
            case DoctorActionsEnum.REGENERATE_NOTE_ID: {
                doctorAction = async (note) => {
                    if (note.id === "root")
                        return; // Root notes are special, preserve them
                    note.id = genUUID();
                    await engine.writeNote(note, {
                        runHooks: false,
                        overrideExisting: true,
                    });
                    numChanges += 1;
                };
                break;
            }
            case DoctorActionsEnum.FIND_BROKEN_LINKS: {
                resp = [];
                doctorAction = async (note) => {
                    const brokenLinks = this.findBrokenLinks(note, noteDicts, engine);
                    if (brokenLinks.length > 0) {
                        resp.push({
                            file: note.fname,
                            vault: VaultUtils.getName(note.vault),
                            links: brokenLinks.map((link) => {
                                return {
                                    value: link.value,
                                    line: link.position?.start.line,
                                    column: link.position?.start.column,
                                };
                            }),
                        });
                        return brokenLinks;
                    }
                    else {
                        return;
                    }
                };
                break;
            }
            case DoctorActionsEnum.FIX_REMOTE_VAULTS: {
                /** Convert a local vault to a remote vault if it is in a git repository and has a remote set. */
                // This action deliberately doesn't set `doctorAction` since it doesn't run per note
                const { wsRoot, vaults } = engine;
                const ctx = "ReloadIndex.convertToRemoteVaultIfPossible";
                const vaultsToFix = (await Promise.all(vaults.map(async (vault) => {
                    const vaultDir = pathForVaultRoot({ wsRoot, vault });
                    const gitPath = path.join(vaultDir, ".git");
                    // Already a remote vault
                    if (vault.remote !== undefined)
                        return;
                    // Not a git repository, nothing to convert
                    if (!(await fs.pathExists(gitPath)))
                        return;
                    const git = new Git({ localUrl: vaultDir });
                    const remoteUrl = await git.getRemoteUrl();
                    // We can't convert if there is no remote
                    if (!remoteUrl)
                        return;
                    return { vault, remoteUrl };
                }))).filter(isNotUndefined);
                if (vaultsToFix.length > 0) {
                    const out = await this.createBackup(wsRoot, DoctorActionsEnum.FIX_SELF_CONTAINED_VAULT_CONFIG);
                    if (out instanceof SailError) {
                        return {
                            exit: true,
                            error: out,
                        };
                    }
                    const workspaceService = new WorkspaceService({ wsRoot });
                    await asyncLoopOneAtATime(vaultsToFix, async ({ vault, remoteUrl }) => {
                        const vaultDir = pathForVaultRoot({ wsRoot, vault });
                        this.L.info({
                            ctx,
                            vaultDir,
                            remoteUrl,
                            msg: "converting local vault to a remote vault",
                        });
                        await workspaceService.markVaultAsRemoteInConfig(vault, remoteUrl);
                    });
                }
                return { exit: true };
            }
            case DoctorActionsEnum.FIX_SELF_CONTAINED_VAULT_CONFIG: {
                /** If a self contained vault was not marked as self contained in the settings, mark it as such. */
                // This action deliberately doesn't set `doctorAction` since it doesn't run per note
                const { wsRoot, vaults } = engine;
                const ctx = "DoctorService.fixSelfContainedVaultConfig";
                const workspaceService = new WorkspaceService({ wsRoot });
                const vaultsToFix = await this.findMisconfiguredSelfContainedVaults(wsRoot, vaults);
                this.L.info({
                    ctx,
                    msg: `Found ${vaultsToFix.length} vaults to fix`,
                    numVaultsToFix: vaultsToFix.length,
                });
                if (vaultsToFix.length > 0) {
                    // We'll be modifying the config so take a backup first
                    const out = await this.createBackup(wsRoot, DoctorActionsEnum.FIX_SELF_CONTAINED_VAULT_CONFIG);
                    if (out instanceof SailError) {
                        return {
                            exit: true,
                            error: out,
                        };
                    }
                    await asyncLoopOneAtATime(vaultsToFix, async (vault) => {
                        const config = workspaceService.config;
                        this.L.info({
                            ctx,
                            vaultName: VaultUtils.getName(vault),
                            msg: "marking vault as self contained vault",
                        });
                        ConfigUtils.updateVault(config, vault, (vault) => {
                            vault.selfContained = true;
                            return vault;
                        });
                        await workspaceService.setConfig(config);
                    });
                }
                workspaceService.dispose();
                return { exit: true };
            }
            case DoctorActionsEnum.FIX_INVALID_FILENAMES: {
                const { canRename, cantRename, stats } = this.findInvalidFileNames({
                    notes,
                    noteDicts,
                });
                resp = stats;
                if (canRename.length > 0) {
                    this.print("Found invalid filename in notes:\n");
                    canRename.forEach((item) => {
                        const { note, resp, cleanedFname } = item;
                        const { fname, vault } = note;
                        const vaultName = VaultUtils.getName(vault);
                        this.print(`Note "${fname}" in ${vaultName} (reason: ${resp.reason})`);
                        this.print(`  Can be automatically fixed to "${cleanedFname}"`);
                    });
                }
                let changes = [];
                if (!dryRun) {
                    changes = await this.fixInvalidFileNames({
                        canRename,
                        engine,
                    });
                }
                if (cantRename.length > 0) {
                    this.print("These notes' filenames cannot be automatically fixed because it will result in duplicate notes:");
                    cantRename.forEach((item) => {
                        const { note, resp, cleanedFname } = item;
                        const { fname, vault } = note;
                        const vaultName = VaultUtils.getName(vault);
                        this.print(`Note "${fname}" in ${vaultName} (reason: ${resp.reason})`);
                        this.print(`  Note "${cleanedFname}" already exists.`);
                    });
                }
                const changeCounts = extractNoteChangeEntryCounts(changes);
                resp = {
                    ...resp,
                    ...changeCounts,
                };
                break;
            }
            default:
                throw new SailError({
                    message: "Unexpected Doctor action. If this is something Sail should support, please create an issue on our Github repository.",
                });
        }
        if (doctorAction !== undefined) {
            for (const note of notes) {
                if (numChanges >= limit)
                    break;
                this.L.debug({ msg: `processing ${note.fname}` });
                // eslint-disable-next-line no-await-in-loop
                await doctorAction(note);
            }
        }
        this.L.info({ msg: "doctor done", numChanges });
        if (action === DoctorActionsEnum.FIND_BROKEN_LINKS) {
            this.print(JSON.stringify({ brokenLinks: resp }, null, "  "));
        }
        return { exit, resp };
    }
    /** Returns the path for the backup if it was able to create one, or a SailError if one occurred during backup. */
    async createBackup(wsRoot, backupInfix) {
        try {
            const path = await DConfig.createBackup(wsRoot, backupInfix);
            return path;
        }
        catch (error) {
            return new SailError({
                message: `Backup ${backupInfix} failed. Aborting the Doctor action.`,
                payload: error,
            });
        }
    }
    findInvalidFileNames(opts) {
        const { notes, noteDicts } = opts;
        const validationResps = notes
            // stubs will be automatically handled when their children are renamed
            .filter((note) => {
            return !note.stub;
        })
            .map((note) => {
            const { fname } = note;
            const resp = NoteUtils.validateFname(fname);
            return {
                note,
                resp,
            };
        });
        const invalidResps = validationResps.filter((validationResp) => !validationResp.resp.isValid);
        const stats = {
            numEmptyHierarchy: invalidResps.filter((item) => item.resp.reason === InvalidFilenameReason.EMPTY_HIERARCHY).length,
            numIllegalCharacter: invalidResps.filter((item) => item.resp.reason === InvalidFilenameReason.ILLEGAL_CHARACTER).length,
            numLeadingOrTrailingWhitespace: invalidResps.filter((item) => item.resp.reason ===
                InvalidFilenameReason.LEADING_OR_TRAILING_WHITESPACE).length,
        };
        const [canRename, cantRename] = _.partition(invalidResps.map((item) => {
            const { note } = item;
            const { fname } = note;
            const cleanedFname = NoteUtils.cleanFname({
                fname,
            });
            const canRename = NoteDictsUtils.findByFname({
                fname: cleanedFname,
                noteDicts,
                vault: note.vault,
            }).length === 0;
            return {
                ...item,
                cleanedFname,
                canRename,
            };
        }), (item) => item.canRename);
        return {
            canRename,
            cantRename,
            stats,
        };
    }
    async fixInvalidFileNames(opts) {
        const { canRename, engine } = opts;
        let changes = [];
        if (canRename.length > 0) {
            await asyncLoopOneAtATime(canRename, async (item) => {
                const { note, cleanedFname } = item;
                const { fname, vault } = note;
                const vaultName = VaultUtils.getName(vault);
                const out = await engine.renameNote({
                    oldLoc: {
                        fname,
                        vaultName,
                    },
                    newLoc: {
                        fname: cleanedFname,
                        vaultName,
                    },
                });
                if (out.data) {
                    changes = changes.concat(out.data);
                    this.print(`Note "${fname}" in ${vaultName} renamed to "${cleanedFname}"`);
                }
                if (out.error) {
                    this.print(`Error encountered while renaming "${fname}" in vault ${vaultName}. The filename of this note is still invalid. Please manually rename this note.`);
                }
            });
            this.print("\n");
        }
        return changes;
    }
}
//# sourceMappingURL=service.js.map