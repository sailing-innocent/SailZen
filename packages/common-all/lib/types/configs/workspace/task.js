import { LookupSelectionTypeEnum } from "../../lookup";
import { NoteAddBehaviorEnum } from "./types";
/**
 * Generates default {@link ScratchConfig}
 * @returns ScratchConfig
 */
export function genDefaultTaskConfig() {
    return {
        name: "task",
        dateFormat: "y.MM.dd",
        addBehavior: NoteAddBehaviorEnum.asOwnDomain,
        statusSymbols: {
            "": " ",
            wip: "w",
            done: "x",
            assigned: "a",
            moved: "m",
            blocked: "b",
            delegated: "l",
            dropped: "d",
            pending: "y",
        },
        taskCompleteStatus: ["done", "x"],
        prioritySymbols: {
            H: "high",
            M: "medium",
            L: "low",
        },
        todoIntegration: false,
        createTaskSelectionType: LookupSelectionTypeEnum.selection2link,
    };
}
/** Used to recognize if something is a task note. If any of these are included in the frontmatter, the note will be considered a task note. */
const TASK_NOTE_PROP_KEYS = ["status", "due", "owner", "priority"];
export class TaskNoteUtils {
    static isTaskNote(note) {
        for (const prop of TASK_NOTE_PROP_KEYS) {
            if (note.custom !== undefined && note.custom[prop] !== undefined)
                return true;
        }
        return false;
    }
    static genDefaultTaskNoteProps(note, config) {
        const props = {
            custom: {
                status: "",
                due: "",
                priority: "",
                owner: "",
            },
        };
        if (config.todoIntegration)
            props.custom["TODO"] = note.title;
        return props;
    }
    static getStatusSymbolRaw({ note, taskConfig, }) {
        const { status } = note.custom;
        if (status === undefined)
            return undefined;
        // If the symbol is not mapped to anything, use the symbol prop directly
        if (!taskConfig.statusSymbols)
            return `${status}`;
        const symbol = taskConfig.statusSymbols[status];
        if (symbol === undefined)
            return `${status}`;
        // If it does map to something, then use that
        return `${symbol}`;
    }
    static getStatusSymbol(props) {
        const status = this.getStatusSymbolRaw(props);
        if (status === undefined)
            return undefined;
        return `[${this.getStatusSymbolRaw(props)}]`;
    }
    static isTaskComplete({ note, taskConfig, }) {
        const { status } = note.custom;
        return status && taskConfig.taskCompleteStatus?.includes(status);
    }
    static getPrioritySymbol({ note, taskConfig, }) {
        const { priority } = note.custom;
        if (priority === undefined)
            return undefined;
        // If the symbol is not mapped to anything, use the symbol prop directly
        if (!taskConfig.prioritySymbols)
            return priority;
        const symbol = taskConfig.prioritySymbols[priority];
        if (symbol === undefined)
            return priority;
        // If it does map to something, then use that
        return symbol;
    }
}
//# sourceMappingURL=task.js.map