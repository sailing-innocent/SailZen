import { createLogger } from "@saili/common-server";
import fs from "fs-extra";
import _ from "lodash";
let L;
export function setLogger({ logPath, logLvl, }) {
    const logLevel = logLvl || process.env.LOG_LEVEL || "debug";
    // @ts-ignore
    L = createLogger("sail.server", logPath, { lvl: logLevel });
    return L;
}
export function getLogger() {
    if (!L) {
        const logPath = process.env.LOG_DST || "stdout";
        L = configureLogger({ logPath });
    }
    return L;
}
export function configureLogger(opts) {
    const { logPath, logLvl } = _.defaults(opts, { logPath: "stdout" });
    if (logPath !== "stdout") {
        if (fs.existsSync(logPath)) {
            try {
                fs.moveSync(logPath, `${logPath}.old`, { overwrite: true });
            }
            catch (err) { }
        }
        fs.ensureFileSync(logPath);
    }
    return setLogger({ logPath, logLvl });
}
//# sourceMappingURL=core.js.map