import { ConfigUtils, TaskNoteUtils, VaultUtils, } from "@saili/common-all";
import _ from "lodash";
import { DECORATION_TYPES } from "./utils";
/** Decorates the note `fname` in vault `vaultName` if the note is a task note. */
export async function decorateTaskNote({ engine, range, fname, vaultName, config, }) {
    const taskConfig = ConfigUtils.getTask(config);
    const vault = vaultName && config.workspace.vaults
        ? VaultUtils.getVaultByName({
            vname: vaultName,
            vaults: config.workspace.vaults,
        })
        : undefined;
    const note = (await engine.findNotesMeta({ fname, vault }))[0];
    if (!note || !TaskNoteUtils.isTaskNote(note))
        return;
    // Determines whether the task link is preceded by an empty or full checkbox
    const status = TaskNoteUtils.getStatusSymbol({ note, taskConfig });
    const { due, owner, priority } = note.custom;
    const decorationString = [];
    if (due) {
        decorationString.push(`due:${due}`);
        let due_day = new Date(due).getTime();
        let today = Date.now();
        if (due_day < today) {
            decorationString.push(`overdue`);
        }
        else {
            let days_left = Math.floor((due_day - today) / (1000 * 60 * 60 * 24));
            decorationString.push(`${days_left} days left`);
        }
    }
    if (owner)
        decorationString.push(`@${owner}`);
    if (priority) {
        const prioritySymbol = TaskNoteUtils.getPrioritySymbol({
            note,
            taskConfig,
        });
        if (prioritySymbol)
            decorationString.push(`priority:${prioritySymbol}`);
    }
    if (note.tags) {
        const tags = _.isString(note.tags) ? [note.tags] : note.tags;
        decorationString.push(...tags.map((tag) => `#${tag}`));
    }
    const decoration = {
        type: DECORATION_TYPES.taskNote,
        range,
        beforeText: status ? `${status} ` : undefined,
        afterText: decorationString.length > 0
            ? ` ${decorationString.join(" ")}`
            : undefined,
    };
    return decoration;
}
//# sourceMappingURL=taskNotes.js.map