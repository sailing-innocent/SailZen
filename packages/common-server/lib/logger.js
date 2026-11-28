// import pino from "pino";
import { env } from "@saili/common-all";
import pino from "pino";
export class Logger {
    name;
    level;
    constructor(opts) {
        this.name = opts.name;
        this.level = opts.level;
    }
    _log(msg) {
        let ctx = "";
        if (msg.ctx) {
            ctx = msg.ctx;
        }
        // eslint-disable-next-line no-console
        console.log(this.name, ctx, msg);
    }
    debug = (msg) => {
        this._log(msg);
    };
    info = (msg) => {
        this._log(msg);
    };
    error = (msg) => {
        this._log(msg);
    };
}
/** @deprecated Avoid using this function as it may leak file descriptors. Please see createDisposableLogger instead. */
function createLogger(name, dest, 
// TODO: not using pretty option
opts) {
    const level = opts?.lvl || env("LOG_LEVEL", { shouldThrow: false }) || "info";
    const nameClean = name || env("LOG_NAME", { shouldThrow: false }) || "logger";
    const logDst = dest || env("LOG_DST", { shouldThrow: false }) || "stdout";
    const pinoOpts = { name: nameClean, level };
    if (logDst === "stdout") {
        return pino(pinoOpts);
    }
    else {
        return pino(pino.destination(logDst)).child(pinoOpts);
    }
}
/** Create a logger. The logger **must** be disposed after being used if the function returned a dispose callback, otherwise it will leak file descriptors and may lead to crashes. */
function createDisposableLogger(name, dest, 
// TODO: not using pretty option
opts) {
    const level = opts?.lvl || env("LOG_LEVEL", { shouldThrow: false }) || "info";
    const nameClean = name || env("LOG_NAME", { shouldThrow: false }) || "logger";
    const logDst = dest || env("LOG_DST", { shouldThrow: false }) || "stdout";
    const pinoOpts = { name: nameClean, level };
    if (logDst === "stdout") {
        return { logger: pino(pinoOpts), dispose: () => { } };
    }
    else {
        const destination = pino.destination(logDst);
        return {
            logger: pino(destination).child(pinoOpts),
            dispose: () => destination.destroy(),
        };
    }
}
export { createDisposableLogger, createLogger, pino };
export function logAndThrow(logger, msg) {
    logger.error(msg);
    throw JSON.stringify(msg);
}
//# sourceMappingURL=logger.js.map