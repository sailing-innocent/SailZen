import { SailError, ERROR_STATUS, } from "@saili/common-all";
import { SchemaParserV2, vault2Path } from "@saili/common-server";
import fs from "fs-extra";
import _ from "lodash";
import path from "path";
import YAML from "js-yaml";
export class SchemaParser {
    logger;
    wsRoot;
    constructor({ wsRoot, logger }) {
        this.wsRoot = wsRoot;
        this.logger = logger;
    }
    async parseFile(fpath, root) {
        const fname = path.basename(fpath, ".schema.yml");
        const wsRoot = this.wsRoot;
        const vpath = vault2Path({ vault: root, wsRoot });
        const schemaOpts = YAML.load(await fs.readFile(path.join(vpath, fpath), "utf8"));
        return SchemaParserV2.parseRaw(schemaOpts, { root, fname, wsRoot });
    }
    async parse(fpaths, vault) {
        const ctx = "parse";
        this.logger.info({ ctx, msg: "enter", fpaths, vault });
        const out = await Promise.all(fpaths.flatMap(async (fpath) => {
            try {
                return await this.parseFile(fpath, vault);
            }
            catch (err) {
                let message;
                if (err instanceof Error) {
                    message = err.message;
                }
                const vpath = vault2Path({ wsRoot: this.wsRoot, vault });
                const fullPath = path.join(vpath, fpath);
                return new SailError({
                    message: message || ERROR_STATUS.BAD_PARSE_FOR_SCHEMA,
                    status: ERROR_STATUS.BAD_PARSE_FOR_SCHEMA,
                    payload: { fpath, message, fullPath },
                });
            }
        }));
        const errors = _.filter(out, (ent) => ent instanceof SailError);
        return {
            schemas: _.reject(out, (ent) => ent instanceof SailError),
            errors: _.isEmpty(errors) ? null : errors,
        };
    }
}
//# sourceMappingURL=schemaParser.js.map