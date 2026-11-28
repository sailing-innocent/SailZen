import { Cache, FileSystemCache } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
export declare abstract class SailFileSystemCache<T extends FileSystemCache, V> implements Cache<string, V> {
    protected _cacheContents: T;
    private _cachePath;
    private _noCaching;
    private _logger;
    private _numCacheMisses;
    constructor({ cachePath, noCaching, logger, }: {
        cachePath: string;
        logger: DLogger;
        noCaching?: boolean;
    });
    get numCacheMisses(): number;
    /**
     * Read contents from filesystem including version and cache entries
     * @returns cache contents
     */
    private readFromFileSystem;
    abstract get(key: string): V | undefined;
    abstract set(key: string, data: V): void;
    abstract drop(key: string): void;
    abstract createEmptyCacheContents(): T;
    /**
     * Write contents of cache to file system
     */
    writeToFileSystem(): void;
    /**
     * Delete cache file if it exists
     */
    removeFromFileSystem(): void;
    incrementCacheMiss(): void;
}
