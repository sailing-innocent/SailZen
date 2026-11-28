import { Cache } from "./cache";
export type LruCacheOpts = {
    /** Max number of items to keep in cache. */
    maxItems: number;
};
/**
 *  Least recently used cache implementation. Deletes the least-recently-used
 *  items, when cache max items is reached.
 *  (get methods count toward recently used order) */
export declare class SailLruCache<K extends {}, T extends {}> implements Cache<K, T> {
    private cache;
    constructor(opts: LruCacheOpts);
    get(key: K): T | undefined;
    set(key: K, data: T): void;
    drop(key: K): void;
}
