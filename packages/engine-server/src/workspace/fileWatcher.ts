import chokidar, { ChokidarOptions, FSWatcher } from "chokidar";
import { COMMON_FOLDER_IGNORES } from "@saili/common-server";
import path from "path";
import type { Disposable } from "@saili/common-all";

type SupportedEvents = "add" | "addDir" | "change" | "unlink" | "unlinkDir";

export type FileWatcherAdapter = {
  onDidCreate(callback: (filePath: string) => void): Disposable;
  onDidDelete(callback: (filePath: string) => void): Disposable;
  onDidChange(callback: (filePath: string) => void): Disposable;
};

export class EngineFileWatcher implements FileWatcherAdapter {
  private watcher: FSWatcher;
  constructor(
    base: string,
    pattern: string,
    chokidarOpts?: ChokidarOptions,
    onReady?: () => void
  ) {
    // Chokidar requires paths with globs to use POSIX `/` separators, even on Windows
    const patternWithBase = `${path.posix.normalize(base)}/${pattern}`;
    this.watcher = chokidar.watch(patternWithBase, {

      ignoreInitial: true,
      ignored: COMMON_FOLDER_IGNORES,
      ...chokidarOpts,
    });
    if (onReady) this.watcher.on("ready", onReady);
  }

  private onEvent(
    event: SupportedEvents,
    callback: (filePath: string) => void
  ): Disposable {
    this.watcher.on(event, callback);
    return {
      dispose: () => {
        this.watcher.removeAllListeners(event);
      },
    };
  }

  onDidCreate(callback: (filePath: string) => void) {
    return this.onEvent("add", callback);
  }

  onDidDelete(callback: (filePath: string) => void): Disposable {
    return this.onEvent("unlink", callback);
  }

  onDidChange(callback: (filePath: string) => void): Disposable {
    return this.onEvent("change", callback);
  }
}
