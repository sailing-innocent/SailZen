export declare const global: GlobalConfig;
export declare const test: StageConfig;
export declare const local: StageConfig;
export declare const dev: StageConfig;
export declare const prod: StageConfig;
export declare const config: {
    global: GlobalConfig;
    test: StageConfig;
    local: StageConfig;
    dev: StageConfig;
    prod: StageConfig;
};
type GlobalConfig = {
    LOG_LEVEL?: string;
    LOG_NAME?: string;
    LOG_DST?: string;
};
type StageConfig = {
    COGNITO_POOL_ID: string;
    COGNITO_CLIENT_ID: string;
    SEGMENT_WEB_KEY: string;
    SEGMENT_VSCODE_KEY: string;
};
export type ConfigKey = keyof GlobalConfig | keyof StageConfig;
export {};
