export type DLogger = {
    name?: string;
    level: any;
    debug: (msg: any) => void;
    info: (msg: any) => void;
    error: (msg: any) => void;
};
/**
 * A simple DLogger implementation that just logs to console. This logger works
 * on all platforms.
 */
export declare class ConsoleLogger implements DLogger {
    name?: string | undefined;
    level: any;
    debug(msg: any): void;
    info(msg: any): void;
    error(msg: any): void;
}
