import { CleanSailPublishingConfig, DeepPartial, SailPublishingConfig, RespV3, RespWithOptError, SailConfig } from "@saili/common-all";
export declare enum LocalConfigScope {
    WORKSPACE = "WORKSPACE",
    GLOBAL = "GLOBAL"
}
export declare class DConfig {
    static createSync({ wsRoot, defaults, }: {
        wsRoot: string;
        defaults?: DeepPartial<SailConfig>;
    }): SailConfig;
    static configPath(configRoot: string): string;
    static configOverridePath(wsRoot: string, scope: LocalConfigScope): string;
    /**
     * Get without filling in defaults
     * @param wsRoot
     */
    static getRaw(wsRoot: string, overwriteDuplcate?: boolean): Partial<SailConfig>;
    static getOrCreate(sailRoot: string, defaults?: DeepPartial<SailConfig>): SailConfig;
    static getSiteIndex(sconfig: SailPublishingConfig): string;
    /**
     * fill in defaults
     */
    static cleanPublishingConfig(config: SailPublishingConfig): CleanSailPublishingConfig;
    static setCleanPublishingConfig(opts: {
        config: SailConfig;
        cleanConfig: SailPublishingConfig;
    }): void;
    /**
     * See if a local config file is present
     */
    static searchLocalConfigSync(wsRoot: string): RespV3<SailConfig>;
    /**
     * Read configuration
     * @param wsRoot
     * @param useCache: If true, read from cache instead of file system
     * @returns
     */
    static readConfigSync(wsRoot: string, useCache?: boolean): SailConfig;
    /**
     * Read config and merge with local config
     * @param wsRoot
     * @param useCache: If true, read from cache instead of file system
     * @returns
     */
    static readConfigAndApplyLocalOverrideSync(wsRoot: string, useCache?: boolean): RespWithOptError<SailConfig>;
    static writeConfig({ wsRoot, config, }: {
        wsRoot: string;
        config: SailConfig;
    }): Promise<void>;
    static writeLocalConfig({ wsRoot, config, configScope, }: {
        wsRoot: string;
        config: DeepPartial<SailConfig>;
        configScope: LocalConfigScope;
    }): Promise<void>;
    /**
     * Sanity check local config properties
     */
    static validateLocalConfig({ config, }: {
        config: DeepPartial<SailConfig>;
    }): RespV3<boolean>;
    /**
     * Create a backup of sail.yml with an optional custom infix string.
     * e.g.) createBackup(wsRoot, "foo") will result in a backup file name
     * `sail.yyyy.MM.dd.HHmmssS.foo.yml`
     * @param wsRoot workspace root
     * @param infix custom string used in the backup name
     * ^fd66z8uiuczz
     */
    static createBackup(wsRoot: string, infix?: string): Promise<string>;
}
