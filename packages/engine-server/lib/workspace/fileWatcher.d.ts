import { ChokidarOptions } from "chokidar";
import type { Disposable } from "@saili/common-all";
export type FileWatcherAdapter = {
    onDidCreate(callback: (filePath: string) => void): Disposable;
    onDidDelete(callback: (filePath: string) => void): Disposable;
    onDidChange(callback: (filePath: string) => void): Disposable;
};
export declare class EngineFileWatcher implements FileWatcherAdapter {
    private watcher;
    constructor(base: string, pattern: string, chokidarOpts?: ChokidarOptions, onReady?: () => void);
    private onEvent;
    onDidCreate(callback: (filePath: string) => void): Disposable;
    onDidDelete(callback: (filePath: string) => void): Disposable;
    onDidChange(callback: (filePath: string) => void): Disposable;
}
