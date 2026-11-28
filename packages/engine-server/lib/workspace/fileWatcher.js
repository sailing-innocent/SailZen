import chokidar from "chokidar";
import { COMMON_FOLDER_IGNORES } from "@saili/common-server";
import path from "path";
export class EngineFileWatcher {
    watcher;
    constructor(base, pattern, chokidarOpts, onReady) {
        // Chokidar requires paths with globs to use POSIX `/` separators, even on Windows
        const patternWithBase = `${path.posix.normalize(base)}/${pattern}`;
        this.watcher = chokidar.watch(patternWithBase, {
            ignoreInitial: true,
            ignored: COMMON_FOLDER_IGNORES,
            ...chokidarOpts,
        });
        if (onReady)
            this.watcher.on("ready", onReady);
    }
    onEvent(event, callback) {
        this.watcher.on(event, callback);
        return {
            dispose: () => {
                this.watcher.removeAllListeners(event);
            },
        };
    }
    onDidCreate(callback) {
        return this.onEvent("add", callback);
    }
    onDidDelete(callback) {
        return this.onEvent("unlink", callback);
    }
    onDidChange(callback) {
        return this.onEvent("change", callback);
    }
}
//# sourceMappingURL=fileWatcher.js.map