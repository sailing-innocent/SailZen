import _ from "lodash";
import { SailFileSystemCache } from "./sailFileSystemCache";
export class NotesFileSystemCache extends SailFileSystemCache {
    get(key) {
        return this._cacheContents.notes[key];
    }
    set(key, value) {
        this._cacheContents.notes[key] = value;
    }
    drop(key) {
        delete this._cacheContents.notes[key];
    }
    getCacheEntryKeys() {
        return new Set(_.keys(this._cacheContents.notes));
    }
    createEmptyCacheContents() {
        return { version: 0, notes: {} };
    }
}
//# sourceMappingURL=notesFileSystemCache.js.map