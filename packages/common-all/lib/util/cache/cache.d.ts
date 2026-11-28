/** Cache interface. */
export interface Cache<K, T> {
    /** returns data object if a the given key is found; undefined otherwise. */
    get(key: K): T | undefined;
    /** Set the given data, potentially removing a different item depending
     *  on cache implementation and cache state. */
    set(key: K, data: T): void;
    /** Drops the element if it exists in the cache.
     *  NO-OP if the element does not exist. */
    drop(key: K): void;
}
/** Null object implementation of {@link Cache} to be used when we
 *  dont want the code to actually use the cache. */
export declare class NullCache<K, T> implements Cache<K, T> {
    get(_key: K): T | undefined;
    set(_key: K, _data: T): void;
    drop(_key: K): void;
}
