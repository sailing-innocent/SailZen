import { RespV3 } from "./types";
/** Return current nanoseconds. */
export declare const nanos: () => number;
/** Converts the given nano seconds to milliseconds */
export declare const nanosToMillis: (nanos: number) => number;
/**
 * Returns a number representing the milliseconds elapsed
 * between 1 January 1970 00:00:00 UTC and the given date */
export declare const milliseconds: () => number;
export declare class TimeUtils {
    static sleep(ms: number): Promise<unknown>;
    static awaitWithLimit<T>(opts: {
        limitMs: number;
    }, cb: () => Promise<T>): Promise<RespV3<T>>;
}
