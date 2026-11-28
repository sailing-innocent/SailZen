import fs from "fs-extra";
export class SailFileSystemCache {
    _cacheContents;
    _cachePath;
    _noCaching;
    _logger;
    _numCacheMisses;
    constructor({ cachePath, noCaching, logger, }) {
        this._cachePath = cachePath;
        this._noCaching = noCaching;
        this._logger = logger;
        this._numCacheMisses = 0;
        if (this._noCaching) {
            this._cacheContents = this.createEmptyCacheContents();
        }
        else {
            this._cacheContents = this.readFromFileSystem();
        }
    }
    get numCacheMisses() {
        return this._numCacheMisses;
    }
    /**
     * Read contents from filesystem including version and cache entries
     * @returns cache contents
     */
    readFromFileSystem() {
        const ctx = "SailFileSystemCache:readFromFileSystem";
        if (fs.existsSync(this._cachePath)) {
            try {
                return fs.readJSONSync(this._cachePath);
            }
            catch (_err) {
                this._logger.error({ ctx, _err });
                return this.createEmptyCacheContents();
            }
        }
        else {
            return this.createEmptyCacheContents();
        }
    }
    /**
     * Write contents of cache to file system
     */
    writeToFileSystem() {
        if (!this._noCaching) {
            return fs.writeJSONSync(this._cachePath, this._cacheContents);
        }
        return;
    }
    /**
     * Delete cache file if it exists
     */
    removeFromFileSystem() {
        this.createEmptyCacheContents();
        if (fs.pathExistsSync(this._cachePath)) {
            return fs.removeSync(this._cachePath);
        }
        return;
    }
    incrementCacheMiss() {
        this._numCacheMisses += 1;
    }
}
//# sourceMappingURL=sailFileSystemCache.js.map