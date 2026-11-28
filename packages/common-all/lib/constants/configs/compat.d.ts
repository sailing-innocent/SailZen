export type ConfigMapping = {
    clientVersion: string;
    softMapping?: boolean;
};
export declare const CONFIG_TO_MINIMUM_COMPAT_MAPPING: {
    [key: number]: ConfigMapping;
};
export declare class CompatUtils {
    static isSoftMapping(opts: {
        configVersion: number;
    }): boolean;
}
