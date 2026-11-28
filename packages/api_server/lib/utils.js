import { SailError, ERROR_SEVERITY, ERROR_STATUS, stringifyError, } from "@saili/common-all";
import { createLogger } from "@saili/common-server";
import _ from "lodash";
import path from "path";
import { fileURLToPath } from "url";
import { launchv2 } from ".";
import { MemoryStore } from "./store/memoryStore";
/**
 * ESM-compatible replacement for __dirname
 * @param importMetaUrl - import.meta.url from the calling module
 * @returns The directory path of the current module
 */
export function getDirname(importMetaUrl) {
    return path.dirname(fileURLToPath(importMetaUrl));
}
export function getWSKey(uri) {
    return _.trimEnd(uri, "/").toLowerCase();
}
export async function putWS({ ws, engine }) {
    MemoryStore.instance().put(`ws:${getWSKey(ws)}`, engine);
}
export async function getWSEngine({ ws }) {
    const engine = await MemoryStore.instance().get(`ws:${getWSKey(ws)}`);
    if (!engine) {
        throw `No Engine: ${ws}`;
    }
    return engine;
}
export var SubProcessExitType;
(function (SubProcessExitType) {
    SubProcessExitType["EXIT"] = "exit";
    SubProcessExitType["SIGINT"] = "SIGINT";
    SubProcessExitType["SIGURS1"] = "SIGUSR1";
    SubProcessExitType["SIGURS2"] = "SIGUSR2";
    SubProcessExitType["UNCAUGHT_EXCEPTION"] = "uncaughtException";
})(SubProcessExitType || (SubProcessExitType = {}));
export class ServerUtils {
    static onProcessExit({ subprocess, cb, }) {
        subprocess.on("exit", () => cb(SubProcessExitType.EXIT));
        subprocess.on("SIGINT", () => cb(SubProcessExitType.SIGINT));
        // catches "kill pid" (for example: nodemon restart)
        subprocess.on("SIGUSR1", () => cb(SubProcessExitType.SIGURS1));
        subprocess.on("SIGUSR2", () => cb(SubProcessExitType.SIGURS2));
        //catches uncaught exceptions
        subprocess.on("uncaughtException", () => cb(SubProcessExitType.UNCAUGHT_EXCEPTION));
    }
    /**
     * Attach to a server process to kill it when the current process exits
     * @param subprocess
     */
    static cleanServerProcess(subprocess) {
        const handleExit = () => {
            console.log("handle exit");
            try {
                if (subprocess.pid) {
                    process.kill(subprocess.pid);
                }
            }
            catch (err) {
                // this means process was already killed
                if (err.code !== "ESRCH") {
                    console.log("process already killed");
                    throw err;
                }
            }
        };
        ServerUtils.onProcessExit({ subprocess, cb: handleExit });
    }
    static prepareServerArgs() {
        const { NEXT_SERVER_URL, NEXT_STATIC_ROOT, ENGINE_SERVER_PORT, LOG_PATH, } = process.env;
        if (_.some(["LOG_PATH"], (k) => {
            return _.isUndefined(process.env[k]);
        })) {
            throw new SailError({
                message: "no value found for env variable",
                status: ERROR_STATUS.INVALID_CONFIG,
            });
        }
        const logPath = LOG_PATH;
        let port;
        if (ENGINE_SERVER_PORT) {
            port = parseInt(ENGINE_SERVER_PORT, 10);
        }
        const nextServerUrl = NEXT_SERVER_URL;
        const nextStaticRoot = NEXT_STATIC_ROOT;
        return {
            port,
            logPath,
            nextServerUrl,
            nextStaticRoot,
        };
    }
    /**
     * Launch engine server
     * @param
     * @returns
     */
    static async startServerNode({ logPath, nextServerUrl, nextStaticRoot, port, }) {
        const { port: finalPort } = await launchv2({
            port,
            logPath: path.join(logPath, "sail.server.log"),
            nextServerUrl,
            nextStaticRoot,
        });
        if (!process.send) {
            throw new SailError({ message: "expect a child process" });
        }
        process.send(`${finalPort}`);
        return { port: finalPort };
    }
    /**
     * Create a subprocess with a running instance of the engine server
     * @returns
     */
    static async execServerNode({ scriptPath, logPath, nextServerUrl, nextStaticRoot, port, }) {
        const logger = createLogger("execServer", path.join(logPath, "sail.log"));
        const execa = await import("execa");
        return new Promise((resolve, reject) => {
            logger.info({ state: "enter" });
            const subprocess = execa.execaNode(scriptPath, {
                env: {
                    LOG_PATH: logPath,
                    ENGINE_SERVER_PORT: port,
                    NEXT_SERVER_URL: nextServerUrl,
                    NEXT_STATIC_ROOT: nextStaticRoot,
                    ELECTRON_RUN_AS_NODE: 1,
                },
            });
            logger.info({ state: "post:exec.node" });
            subprocess.on("close", (code) => {
                logger.error({ state: "close" });
                reject(new SailError({ message: "close", payload: { code } }));
            });
            subprocess.on("disconnect", () => {
                logger.error({ state: "disconnect" });
                reject(new SailError({ message: "disconnect" }));
            });
            subprocess.on("exit", (code) => {
                logger.error({ state: "exit" });
                reject(new SailError({ message: "exit", payload: { code } }));
            });
            subprocess.on("error", (err) => {
                logger.error({ state: "error", payload: err });
                reject(new SailError({ message: "error", payload: stringifyError(err) }));
            });
            subprocess.on("message", (message) => {
                logger.info({ state: "message", message });
                const port = parseInt(message, 10);
                if (port <= 0) {
                    reject({
                        error: new SailError({
                            message: "port is smaller than 0",
                            severity: ERROR_SEVERITY.FATAL,
                        }),
                    });
                }
                resolve({ port, subprocess });
            });
            this.cleanServerProcess(subprocess);
        });
    }
}
export var ProcessReturnType;
(function (ProcessReturnType) {
    ProcessReturnType["ERROR"] = "error";
})(ProcessReturnType || (ProcessReturnType = {}));
//# sourceMappingURL=utils.js.map