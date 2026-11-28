import { Disposable } from "@saili/common-all";
import pino from "pino";
export type LogLvl = "debug" | "info" | "error" | "warn" | "fatal";
export declare class Logger {
    name: string;
    level: string;
    constructor(opts: {
        name: string;
        level: string;
    });
    private _log;
    debug: (msg: any) => void;
    info: (msg: any) => void;
    error: (msg: any) => void;
}
/** @deprecated Avoid using this function as it may leak file descriptors. Please see createDisposableLogger instead. */
declare function createLogger(name?: string, dest?: string, opts?: {
    lvl?: LogLvl;
}): pino.Logger;
/** Create a logger. The logger **must** be disposed after being used if the function returned a dispose callback, otherwise it will leak file descriptors and may lead to crashes. */
declare function createDisposableLogger(name?: string, dest?: string, opts?: {
    lvl?: LogLvl;
}): {
    logger: pino.Logger;
} & Disposable;
export type DLogger = {
    name?: string;
    level: any;
    debug: (msg: any) => void;
    info: (msg: any) => void;
    error: (msg: any) => void;
};
export { createDisposableLogger, createLogger, pino };
export declare function logAndThrow(logger: Logger, msg: any): never;
