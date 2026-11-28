import { Application } from "express";
export declare function appModule({ logPath, nextServerUrl, nextStaticRoot, }: {
    logPath: string;
    nextServerUrl?: string;
    nextStaticRoot?: string;
}): Application;
