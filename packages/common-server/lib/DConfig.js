import { ConfigUtils, CONSTANTS, SailError, ErrorFactory, ErrorUtils, ERROR_STATUS, getStage, GithubEditViewModeEnum, YamlUtils, } from "@saili/common-all";
import fs from "fs-extra";
import _ from "lodash";
import os from "os";
import path from "path";
import { BackupKeyEnum, BackupService } from "./backup";
import { DConfigLegacy } from "./oneoff/ConfigCompat";
import { readYAML, writeYAML, writeYAMLAsync, readString } from "./files";
export var LocalConfigScope;
(function (LocalConfigScope) {
    LocalConfigScope["WORKSPACE"] = "WORKSPACE";
    LocalConfigScope["GLOBAL"] = "GLOBAL";
})(LocalConfigScope || (LocalConfigScope = {}));
let _sailConfig;
export class DConfig {
    static createSync({ wsRoot, defaults, }) {
        const configPath = DConfig.configPath(wsRoot);
        const config = ConfigUtils.genLatestConfig(defaults);
        writeYAML(configPath, config);
        return config;
    }
    static configPath(configRoot) {
        return path.join(configRoot, CONSTANTS.SAIL_CONFIG_FILE);
    }
    static configOverridePath(wsRoot, scope) {
        const configPath = scope === LocalConfigScope.GLOBAL ? os.homedir() : wsRoot;
        return path.join(configPath, CONSTANTS.SAIL_LOCAL_CONFIG_FILE);
    }
    /**
     * Get without filling in defaults
     * @param wsRoot
     */
    static getRaw(wsRoot, overwriteDuplcate) {
        const configPath = DConfig.configPath(wsRoot);
        const config = readYAML(configPath, overwriteDuplcate ?? false);
        return config;
    }
    static getOrCreate(sailRoot, defaults) {
        const configPath = DConfig.configPath(sailRoot);
        // Need merge here to recursively merge nested configs
        let config = _.merge(ConfigUtils.genDefaultConfig(), defaults);
        if (!fs.existsSync(configPath)) {
            writeYAML(configPath, config);
        }
        else {
            config = {
                ...config,
                ...readYAML(configPath),
            };
        }
        return config;
    }
    static getSiteIndex(sconfig) {
        const { siteIndex, siteHierarchies } = sconfig;
        return siteIndex || siteHierarchies[0];
    }
    /**
     * fill in defaults
     */
    static cleanPublishingConfig(config) {
        const out = _.defaultsDeep(config, {
            copyAssets: true,
            enablePrettyRefs: true,
            siteFaviconPath: "favicon.ico",
            github: {
                enableEditLink: true,
                editLinkText: "Edit this page on Github",
                editBranch: "main",
                editViewMode: GithubEditViewModeEnum.edit,
            },
            writeStubs: true,
            seo: {
                description: "Personal Knowledge Space",
            },
        });
        const { siteRootDir, siteHierarchies } = out;
        let { siteIndex, siteUrl } = out;
        if (process.env["SITE_URL"]) {
            siteUrl = process.env["SITE_URL"];
        }
        if (!siteRootDir) {
            throw new SailError({ message: "siteRootDir is undefined" });
        }
        if (!siteUrl && getStage() === "dev") {
            // this gets overridden in dev so doesn't matter
            siteUrl = "https://foo";
        }
        if (!siteUrl) {
            throw SailError.createFromStatus({
                status: ERROR_STATUS.INVALID_CONFIG,
                message: "siteUrl is undefined. See https://sail.so/notes/f2ed8639-a604-4a9d-b76c-41e205fb8713.html#siteurl for more details",
            });
        }
        if (_.size(siteHierarchies) < 1) {
            throw SailError.createFromStatus({
                status: ERROR_STATUS.INVALID_CONFIG,
                message: `siteHiearchies must have at least one hierarchy`,
            });
        }
        siteIndex = this.getSiteIndex(config);
        return {
            ...out,
            siteIndex,
            siteUrl,
        };
    }
    static setCleanPublishingConfig(opts) {
        const { config, cleanConfig } = opts;
        ConfigUtils.setProp(config, "publishing", cleanConfig);
    }
    /**
     * See if a local config file is present
     */
    static searchLocalConfigSync(wsRoot) {
        const wsPath = path.join(wsRoot, CONSTANTS.SAIL_LOCAL_CONFIG_FILE);
        const globalPath = path.join(os.homedir(), CONSTANTS.SAIL_LOCAL_CONFIG_FILE);
        let foundPath;
        if (fs.existsSync(globalPath)) {
            foundPath = globalPath;
        }
        if (fs.existsSync(wsPath)) {
            foundPath = wsPath;
        }
        if (foundPath) {
            // TODO: do validation in the future
            const data = readYAML(foundPath);
            return { data };
        }
        return {
            error: ErrorFactory.create404Error({
                url: CONSTANTS.SAIL_LOCAL_CONFIG_FILE,
            }),
        };
    }
    /**
     * Read configuration
     * @param wsRoot
     * @param useCache: If true, read from cache instead of file system
     * @returns
     */
    static readConfigSync(wsRoot, useCache) {
        if (_sailConfig && useCache) {
            return _sailConfig;
        }
        const configPath = DConfig.configPath(wsRoot);
        const sailConfigResult = readString(configPath)
            .andThen((input) => YamlUtils.fromStr(input, true))
            .andThen((unknownconfig) => {
            const cleanConfig = DConfigLegacy.configIsV4(unknownconfig)
                ? DConfigLegacy.v4ToV5(unknownconfig)
                : _.defaultsDeep(unknownconfig, ConfigUtils.genDefaultConfig());
            return ConfigUtils.parse(cleanConfig);
        })
            .map((sailConfig) => {
            _sailConfig = sailConfig;
            return sailConfig;
        });
        if (sailConfigResult.isErr()) {
            throw sailConfigResult.error;
        }
        return sailConfigResult.value;
    }
    /**
     * Read config and merge with local config
     * @param wsRoot
     * @param useCache: If true, read from cache instead of file system
     * @returns
     */
    static readConfigAndApplyLocalOverrideSync(wsRoot, useCache) {
        const config = this.readConfigSync(wsRoot, useCache);
        const maybeLocalConfig = this.searchLocalConfigSync(wsRoot);
        let localConfigValidOrError = true;
        if (maybeLocalConfig.data) {
            const respValidate = this.validateLocalConfig({
                config: maybeLocalConfig.data,
            });
            if (respValidate.error) {
                localConfigValidOrError = respValidate.error;
            }
            if (!respValidate.error) {
                _.mergeWith(config, maybeLocalConfig.data, (objValue, srcValue) => {
                    // TODO: optimize, check for keys of known arrays instead
                    if (_.isArray(objValue)) {
                        return srcValue.concat(objValue);
                    }
                    return;
                });
            }
        }
        return {
            data: config,
            error: ErrorUtils.isSailError(localConfigValidOrError)
                ? localConfigValidOrError
                : undefined,
        };
    }
    static writeConfig({ wsRoot, config, }) {
        _sailConfig = config;
        const configPath = DConfig.configPath(wsRoot);
        return writeYAMLAsync(configPath, config);
    }
    static writeLocalConfig({ wsRoot, config, configScope, }) {
        const configPath = DConfig.configOverridePath(wsRoot, configScope);
        return writeYAMLAsync(configPath, config);
    }
    /**
     * Sanity check local config properties
     */
    static validateLocalConfig({ config, }) {
        if (config.workspace) {
            if (_.isEmpty(config.workspace) ||
                (config.workspace.vaults && !_.isArray(config.workspace.vaults))) {
                return {
                    error: new SailError({
                        message: "workspace must not be empty and vaults must be an array if workspace is set",
                    }),
                };
            }
        }
        return { data: true };
    }
    /**
     * Create a backup of sail.yml with an optional custom infix string.
     * e.g.) createBackup(wsRoot, "foo") will result in a backup file name
     * `sail.yyyy.MM.dd.HHmmssS.foo.yml`
     * @param wsRoot workspace root
     * @param infix custom string used in the backup name
     * ^fd66z8uiuczz
     */
    static async createBackup(wsRoot, infix) {
        const backupService = new BackupService({ wsRoot });
        try {
            const configPath = DConfig.configPath(wsRoot);
            const backupResp = await backupService.backup({
                key: BackupKeyEnum.config,
                pathToBackup: configPath,
                timestamp: true,
                infix,
            });
            if (backupResp.error) {
                throw new SailError({ ...backupResp.error });
            }
            return backupResp.data;
        }
        finally {
            backupService.dispose();
        }
    }
}
//# sourceMappingURL=DConfig.js.map