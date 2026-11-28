/** Null object implementation of {@link Cache} to be used when we
 *  dont want the code to actually use the cache. */
export class NullCache {
    get(_key) {
        return undefined;
    }
    set(_key, _data) {
        // Empty since this is null object implementation
    }
    drop(_key) {
        // Empty since this is null object implementation
    }
}
//# sourceMappingURL=cache.js.map