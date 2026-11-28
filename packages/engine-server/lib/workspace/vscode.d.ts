import { DVault, WorkspaceExtensionSetting, WorkspaceSettings } from "@saili/common-all";
export type CodeConfigChanges = {
    settings?: ConfigChanges;
    extensions?: CodeExtensionsConfig;
    snippetChanges?: any;
};
type CodeExtensionsConfig = {
    recommendations?: string[];
    unwantedRecommendations?: string[];
};
export type ConfigChanges = {
    add: [];
    errors: [];
};
type ConfigUpdateEntry = {
    /**
     * Config default
     */
    default: any;
    action?: "ADD" | "REMOVE";
};
export type ConfigUpdateChangeSet = {
    [k: string]: ConfigUpdateEntry;
};
export type SettingsUpgradeOpts = {
    force?: boolean;
};
export declare const _SETTINGS: ConfigUpdateChangeSet;
export type WriteConfigOpts = {
    vaults?: DVault[];
    overrides?: Partial<WorkspaceSettings>;
};
export declare class WorkspaceConfig {
    static genDefaults(): WorkspaceSettings;
    static workspaceFile(wsRoot: string): string;
    /**
     * Create sail.code-workspace file
     * @param wsRoot
     * @param vaults
     * @param opts
     * @returns
     */
    static write(wsRoot: string, vaults?: DVault[], opts?: WriteConfigOpts): void;
}
export declare class Extensions {
    static EXTENSION_FILE_NAME: string;
    static defaults(): WorkspaceExtensionSetting;
    static configEntries(): ConfigUpdateEntry[];
    static update(extensions: CodeExtensionsConfig): CodeExtensionsConfig;
}
type Snippet = {
    prefix: string;
    scope: string;
    body: string | string[];
    description: string;
};
export declare class Snippets {
    static filename: string;
    static defaults: {
        [key: string]: Snippet;
    };
    static create: (dirPath: string) => void;
    static read: (dirPath: string) => Promise<false | {
        [key: string]: Snippet;
    }>;
    static upgradeOrCreate(dirPath: string): Promise<{
        [key: string]: Snippet;
    }>;
    static write(dirPath: string, orig: {
        [key: string]: Snippet;
    }, changed: {
        [key: string]: Snippet;
    }): void;
}
export declare class Settings {
    private static getDefaults;
    static configEntries(): ConfigUpdateChangeSet;
    static defaults(): {
        [x: string]: any;
    };
    static defaultsChangeSet(): ConfigUpdateChangeSet;
}
export {};
