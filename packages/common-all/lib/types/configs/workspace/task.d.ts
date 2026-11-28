import { LookupSelectionType } from "../../lookup";
import { NoteProps, NotePropsMeta } from "../../foundation";
import { JournalConfig } from "./journal";
/**
 * Namespace for configuring scratch note behavior
 */
export type TaskConfig = Pick<JournalConfig, "name" | "dateFormat" | "addBehavior"> & {
    /** Maps each status to a symbol, word, or sentence. This will be displayed for the task. */
    statusSymbols: {
        [status: string]: string;
    };
    /** Sets which statuses mark the task as completed. */
    taskCompleteStatus: string[];
    /** Maps each priority to a symbol, word, or sentence. This will be displayed for the task. */
    prioritySymbols: {
        [status: string]: string;
    };
    /** Add a "TODO: <note title>" entry to the frontmatter of task notes. This can simplify integration with various Todo extensions like Todo Tree. */
    todoIntegration: boolean;
    /** The default selection type to use in Create Task Note command. */
    createTaskSelectionType: LookupSelectionType;
};
/**
 * Generates default {@link ScratchConfig}
 * @returns ScratchConfig
 */
export declare function genDefaultTaskConfig(): TaskConfig;
export type TaskNoteProps = {
    custom: {
        status?: string;
        due?: string;
        owner?: string;
        priority?: string;
        TODO?: string;
        DONE?: string;
    };
};
export declare class TaskNoteUtils {
    static isTaskNote(note: NotePropsMeta): note is NotePropsMeta & TaskNoteProps;
    static genDefaultTaskNoteProps(note: NoteProps, config: TaskConfig): TaskNoteProps;
    static getStatusSymbolRaw({ note, taskConfig, }: {
        note: TaskNoteProps;
        taskConfig: TaskConfig;
    }): string | undefined;
    static getStatusSymbol(props: {
        note: TaskNoteProps;
        taskConfig: TaskConfig;
    }): string | undefined;
    static isTaskComplete({ note, taskConfig, }: {
        note: TaskNoteProps;
        taskConfig: TaskConfig;
    }): boolean | "" | undefined;
    static getPrioritySymbol({ note, taskConfig, }: {
        note: TaskNoteProps;
        taskConfig: TaskConfig;
    }): string | undefined;
}
