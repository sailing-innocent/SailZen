import { NotesCache, NotesCacheEntry } from "@saili/common-all";
import { SailFileSystemCache } from "./sailFileSystemCache";
export declare class NotesFileSystemCache extends SailFileSystemCache<NotesCache, NotesCacheEntry> {
    get(key: string): NotesCacheEntry | undefined;
    set(key: string, value: NotesCacheEntry): void;
    drop(key: string): void;
    getCacheEntryKeys(): Set<string>;
    createEmptyCacheContents(): NotesCache;
}
