import { ConfigKey } from "./config";
import { Stage } from "./types";
export declare function getStage(): Stage;
export declare function getOrThrow<T = any>(obj: T, k: keyof T, opts?: {
    shouldThrow?: boolean;
}): T[keyof T];
export declare function setStageIfUndefined(newStage: Stage): void;
export declare function setEnv(name: ConfigKey, value: any): void;
export declare function env(name: ConfigKey, opts?: {
    shouldThrow?: boolean;
}): any;
/**
 * Various utilities that are not categorized
 */
export declare class RuntimeUtils {
    static isRunningInTestOrCI(): boolean;
    /**
     * Check if running inside test context
     */
    static isRunningInsideTest(): boolean;
    /**
     * Check if process is running inside a CI
     */
    static isRunningInsideCI(): boolean;
}
