import { CONSTANTS, SailError, ERROR_SEVERITY, NoteUtils, ConfigUtils, } from "@saili/common-all";
import { createLogger } from "@saili/common-server";
import axios from "axios";
// import execa from "execa";
import fs from "fs-extra";
import _ from "lodash";
import path from "path";
export class HookUtils {
    static addToConfig({ config, hookType, hookEntry, }) {
        const hooks = ConfigUtils.getHooks(config);
        const onCreate = _.get(hooks, hookType, []).concat([hookEntry]);
        const hooksToAdd = hooks || { onCreate: [] };
        hooksToAdd.onCreate = onCreate;
        ConfigUtils.setHooks(config, hooksToAdd);
        return config;
    }
    static getHookDir(wsRoot) {
        return path.join(wsRoot, CONSTANTS.SAIL_HOOKS_BASE);
    }
    static getHookScriptPath({ wsRoot, basename, }) {
        return path.join(wsRoot, CONSTANTS.SAIL_HOOKS_BASE, basename);
    }
    static removeFromConfig({ config, hookType, hookId, }) {
        const hooks = ConfigUtils.getHooks(config);
        let onCreate = _.get(hooks, hookType, []);
        onCreate = _.remove(onCreate, { id: hookId });
        const idx = _.findIndex(onCreate, { id: hookId });
        onCreate.splice(idx, 1);
        const hooksAfterRemove = hooks || { onCreate: [] };
        hooksAfterRemove.onCreate = onCreate;
        ConfigUtils.setHooks(config, hooksAfterRemove);
        return config;
    }
    static requireHook = async ({ note, fpath, wsRoot, }) => {
        const logger = createLogger();
        logger.info({ ctx: "requireHook", msg: "using webpack require" });
        const req = require(`./webpack-require-hack.js`);
        logger.info({ ctx: "requireHook", fpath, wsRoot });
        const execa = await import("execa");
        return await req(fpath)({
            wsRoot,
            note: { ...note },
            execa,
            axios,
            _,
            NoteUtils,
        });
    };
    static validateHook = ({ hook, wsRoot, }) => {
        const scriptPath = hook.id + "." + hook.type;
        const hookPath = HookUtils.getHookScriptPath({
            wsRoot,
            basename: scriptPath,
        });
        if (!fs.existsSync(hookPath)) {
            return {
                error: new SailError({
                    severity: ERROR_SEVERITY.MINOR,
                    message: `hook ${hook.id} has missing script. ${hookPath} doesn't exist`,
                }),
                valid: false,
            };
        }
        return { error: null, valid: true };
    };
}
//# sourceMappingURL=hooks.js.map