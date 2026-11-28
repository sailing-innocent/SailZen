import express from "express";
import { fileURLToPath } from "url";
import path from "path";
import { configureLogger, getLogger } from "./core";
import { appModule } from "./Server";
export { ServerUtils, SubProcessExitType } from "./utils";
export { express, launchv2 };
function launchv2(opts) {
    const ctx = "launch";
    const listenPort = opts?.port || 0;
    const LOG_DST = opts?.logPath ? opts.logPath : "stdout";
    configureLogger({ logPath: LOG_DST });
    return new Promise((resolve) => {
        const app = appModule({
            logPath: LOG_DST,
            nextServerUrl: opts?.nextServerUrl,
            nextStaticRoot: opts?.nextStaticRoot,
        });
        const serverSockets = new Set();
        const server = app.listen(listenPort, "localhost", () => {
            const port = server.address().port;
            const __dirname = path.dirname(fileURLToPath(import.meta.url));
            getLogger().info({ ctx, msg: "exit", port, LOG_DST, root: __dirname });
            // delete all active sockets on server close
            server.on("connection", (socket) => {
                serverSockets.add(socket);
                socket.on("close", () => {
                    serverSockets.delete(socket);
                });
            });
            resolve({ port, server, serverSockets });
        });
    });
}
//# sourceMappingURL=index.js.map