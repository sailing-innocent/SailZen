import { LogLvl } from "@saili/common-server";
import express from "express";
import { Socket } from "net";
import { fileURLToPath } from "url";
import path from "path";
import { configureLogger, getLogger } from "./core";
import { appModule } from "./Server";

export { ServerUtils, SubProcessExitType } from "./utils";
export { express, launchv2 };

type LaunchOpts = {
  port?: number;
  logPath?: string;
  logLevel?: LogLvl;
  nextServerUrl?: string;
  nextStaticRoot?: string;
};

export type ServerClose = ReturnType<
  typeof express["application"]["listen"]
>["close"];
export type Server = {
  close: ServerClose;
};

function launchv2(
  opts?: {} & LaunchOpts
): Promise<{ port: number; server: Server; serverSockets: Set<Socket> }> {
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

    const serverSockets = new Set<Socket>();

    const server = app.listen(listenPort, "localhost", () => {
      const port = (server.address() as any).port;
      const __dirname = path.dirname(fileURLToPath(import.meta.url));
      getLogger().info({ ctx, msg: "exit", port, LOG_DST, root: __dirname });

      // delete all active sockets on server close
      server.on("connection", (socket: Socket) => {
        serverSockets.add(socket);
        socket.on("close", () => {
          serverSockets.delete(socket);
        });
      });
      resolve({ port, server, serverSockets });
    });
  });
}
