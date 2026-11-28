import { LRUCache } from "lru-cache";
import { SailError } from "../../error";
/**
 *  Least recently used cache implementation. Deletes the least-recently-used
 *  items, when cache max items is reached.
 *  (get methods count toward recently used order) */
export class SailLruCache {
    cache;
    constructor(opts) {
        if (opts.maxItems <= 0) {
            throw new SailError({
                message: `Max items cannot be less than or equal to 0`,
            });
        }
        this.cache = new LRUCache({
            max: opts.maxItems,
        });
    }
    get(key) {
        return this.cache.get(key);
    }
    set(key, data) {
        this.cache.set(key, data);
    }
    drop(key) {
        this.cache.delete(key);
    }
}
//# sourceMappingURL=lruCache.js.map