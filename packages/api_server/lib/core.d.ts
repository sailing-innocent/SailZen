import { DLogger, LogLvl } from "@saili/common-server";
export declare function setLogger({ logPath, logLvl, }: {
    logPath: string;
    logLvl?: LogLvl;
}): DLogger;
export declare function getLogger(): DLogger;
export declare function configureLogger(opts?: {
    logPath: string;
    logLvl?: LogLvl;
}): DLogger;
