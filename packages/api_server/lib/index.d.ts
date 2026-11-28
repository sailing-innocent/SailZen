import { LogLvl } from "@saili/common-server";
import express from "express";
import { Socket } from "net";
export { ServerUtils, SubProcessExitType } from "./utils";
export { express, launchv2 };
type LaunchOpts = {
    port?: number;
    logPath?: string;
    logLevel?: LogLvl;
    nextServerUrl?: string;
    nextStaticRoot?: string;
};
export type ServerClose = ReturnType<typeof express["application"]["listen"]>["close"];
export type Server = {
    close: ServerClose;
};
declare function launchv2(opts?: {} & LaunchOpts): Promise<{
    port: number;
    server: Server;
    serverSockets: Set<Socket>;
}>;
