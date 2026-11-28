import { DEngine } from "@saili/common-all";
import { Subprocess } from "execa";
/**
 * ESM-compatible replacement for __dirname
 * @param importMetaUrl - import.meta.url from the calling module
 * @returns The directory path of the current module
 */
export declare function getDirname(importMetaUrl: string): string;
export declare function getWSKey(uri: string): string;
export declare function putWS({ ws, engine }: {
    ws: string;
    engine: DEngine;
}): Promise<void>;
export declare function getWSEngine({ ws }: {
    ws: string;
}): Promise<DEngine>;
type ServerArgs = {
    scriptPath: string;
    logPath: string;
    port?: number;
    nextServerUrl?: string;
    nextStaticRoot?: string;
};
export declare enum SubProcessExitType {
    EXIT = "exit",
    SIGINT = "SIGINT",
    SIGURS1 = "SIGUSR1",
    SIGURS2 = "SIGUSR2",
    UNCAUGHT_EXCEPTION = "uncaughtException"
}
export declare class ServerUtils {
    static onProcessExit({ subprocess, cb, }: {
        subprocess: Subprocess;
        cb: (exitType: SubProcessExitType, args?: any) => any;
    }): void;
    /**
     * Attach to a server process to kill it when the current process exits
     * @param subprocess
     */
    static cleanServerProcess(subprocess: Subprocess): void;
    static prepareServerArgs(): {
        port: number | undefined;
        logPath: string;
        nextServerUrl: string | undefined;
        nextStaticRoot: string | undefined;
    };
    /**
     * Launch engine server
     * @param
     * @returns
     */
    static startServerNode({ logPath, nextServerUrl, nextStaticRoot, port, }: Omit<ServerArgs, "scriptPath">): Promise<{
        port: number;
    }>;
    /**
     * Create a subprocess with a running instance of the engine server
     * @returns
     */
    static execServerNode({ scriptPath, logPath, nextServerUrl, nextStaticRoot, port, }: ServerArgs): Promise<{
        port: number;
        subprocess: Subprocess;
    }>;
}
export declare enum ProcessReturnType {
    ERROR = "error"
}
export {};
