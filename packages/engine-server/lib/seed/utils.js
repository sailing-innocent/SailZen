import { ConfigUtils, SailError, ERROR_STATUS, } from "@saili/common-all";
import fs from "fs-extra";
import _ from "lodash";
import path from "path";
import { WorkspaceService } from "../workspace";
import { DEFAULT_SEED_PUBLISHER } from "./constants";
export class SeedUtils {
    static exists({ id, wsRoot }) {
        const seedPath = this.seed2Path({ id, wsRoot });
        return fs.pathExists(seedPath);
    }
    static genDefaultConfig(opts) {
        return _.defaults(opts.seed || {}, {
            id: opts.id,
            name: opts.name,
            publisher: DEFAULT_SEED_PUBLISHER,
            description: "a seed waiting to sprout",
            license: "CC BY 4.0",
            repository: {
                type: "git",
                url: "",
            },
            root: "vault",
        });
    }
    static getSeedId({ publisher, name }) {
        return `${publisher}.${name}`;
    }
    /**
     * Path for seed
     * @param wsRoot - workspace root
     * @param id - id of seed
     * @returns
     */
    static seed2Path({ wsRoot, id }) {
        return path.join(wsRoot, "seeds", id);
    }
    static seed2Vault({ seed }) {
        const id = this.getSeedId(seed);
        return {
            fsPath: seed.root,
            seed: id,
            name: id,
        };
    }
    static validateWorkspaceSeedConversion({ wsRoot }) {
        const config = WorkspaceService.getOrCreateConfig(wsRoot);
        const vaults = ConfigUtils.getVaults(config);
        if (vaults.length !== 1) {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.INVALID_STATE,
                    message: `workspace must have exactly one vault. found ${JSON.stringify(vaults)}`,
                }),
            };
        }
        const workspaces = ConfigUtils.getWorkspace(config).workspaces;
        if (!_.isEmpty(workspaces)) {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.INVALID_STATE,
                    message: "workspace vaults not supported",
                }),
            };
        }
        return {
            error: undefined,
        };
    }
}
//# sourceMappingURL=utils.js.map