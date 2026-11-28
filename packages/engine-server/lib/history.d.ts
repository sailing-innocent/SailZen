import { URI } from "vscode-uri";
export type HistoryEvent = {
    action: HistoryEventAction;
    source: HistoryEventSource;
    /**
     * Used to further narrow down the source.
     * This is used in {@link LookupProvider} as this can be embedded in multiple commands (eg. NoteLookup vs RenameNote)
     * For example, for [RenameNote](https://github.com/sailhq/sail/blob/6c98d466536632530399bd45f1220ae725ff3e2f/packages/plugin-core/src/commands/RenameNoteV2a.ts#L52-L52),
     * the id is "rename" whereas for NoteLookup, the id is "lookup"
     */
    id?: string;
    /**
     * Sometimes events have uris attached to them (eg. {@link HistoryEventAction.create})
     */
    uri?: URI;
    /**
     * Arbitrary data that can be passed to the event
     */
    data?: any;
};
/**
 * Where did the event come from
 */
export type HistoryEventSource = "engine" | "src" | "extension" | "lspServer" | "apiServer" | "lookupProvider" | "watcher";
/**
 * What action was performed
 */
export type HistoryEventAction = "delete" | "create" | "activate" | "initialized" | "not_initialized" | "rename" | "upgraded" | APIServerEvent | "done" | "error" | "changeState";
export type APIServerEvent = "changedPort";
type HistoryEventListenerFunc = (event: HistoryEvent) => void;
type HistoryEventListenerFuncEntry = {
    id: string;
    listener: (event: HistoryEvent) => void;
};
interface IHistoryService {
    readonly events: HistoryEvent[];
    add(event: HistoryEvent): void;
    lookBack(num?: number): HistoryEvent[];
}
/**
 * Keeps of lifecycle events in Sail.
 */
export declare class HistoryService implements IHistoryService {
    readonly events: HistoryEvent[];
    /**
     @deprecated
     */
    subscribers: {
        [k in HistoryEventSource]: HistoryEventListenerFunc[];
    };
    subscribersv2: {
        [k in HistoryEventSource]: HistoryEventListenerFuncEntry[];
    };
    pause: boolean;
    static instance(): HistoryService;
    constructor();
    add(event: HistoryEvent): void;
    remove(id: string, source: HistoryEventSource): void;
    clearSubscriptions(): void;
    lookBack(num?: number): HistoryEvent[];
    subscribe(source: HistoryEventSource, func: HistoryEventListenerFunc): void;
    subscribev2(source: HistoryEventSource, ent: HistoryEventListenerFuncEntry): void;
}
export {};
