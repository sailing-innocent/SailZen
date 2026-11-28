import fs from "fs-extra";
import { SailError, ERROR_SEVERITY, ERROR_STATUS, } from "@saili/common-all";
import _ from "lodash";
import { getAllFiles } from "@saili/common-server";
export class NodeJSFileStore {
    /**
     * See {@link IFileStore.read}
     */
    async read(uri) {
        try {
            const data = await fs.readFile(uri.fsPath, { encoding: "utf8" });
            return { data };
        }
        catch (err) {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.CONTENT_NOT_FOUND,
                    message: `Failed to read from ${uri.fsPath}.`,
                    innerError: err,
                    severity: ERROR_SEVERITY.MINOR,
                }),
            };
        }
    }
    /**
     * See {@link IFileStore.readDir}
     */
    async readDir(opts) {
        const { root } = _.defaults(opts, {
            exclude: [".git", "Icon\r", ".*"],
        });
        try {
            const resp = await getAllFiles(opts);
            if (resp.error) {
                return { error: resp.error };
            }
            else if (resp.data) {
                return { data: resp.data };
            }
            else {
                return { data: [] };
            }
        }
        catch (err) {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.CONTENT_NOT_FOUND,
                    message: `Failed to read from ${root}.`,
                    innerError: err,
                    severity: ERROR_SEVERITY.MINOR,
                }),
            };
        }
    }
    /**
     * See {@link IFileStore.write}
     */
    async write(uri, content) {
        try {
            await fs.writeFile(uri.fsPath, content);
            return { data: uri };
        }
        catch (err) {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.WRITE_FAILED,
                    message: `Failed to write to ${uri.fsPath}.`,
                    innerError: err,
                    severity: ERROR_SEVERITY.MINOR,
                }),
            };
        }
    }
    /**
     * See {@link IFileStore.delete}
     */
    async delete(uri) {
        try {
            if (await fs.pathExists(uri.fsPath)) {
                await fs.unlink(uri.fsPath);
            }
            return { data: uri };
        }
        catch (err) {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.DELETE_FAILED,
                    message: `Failed to delete from ${uri.fsPath}.`,
                    innerError: err,
                    severity: ERROR_SEVERITY.MINOR,
                }),
            };
        }
    }
    /**
     * See {@link IFileStore.rename}
     */
    async rename(oldUri, newUri) {
        try {
            await fs.rename(oldUri.fsPath, newUri.fsPath);
            return { data: newUri };
        }
        catch (err) {
            return {
                error: SailError.createFromStatus({
                    status: ERROR_STATUS.RENAME_FAILED,
                    message: `Failed to rename from ${oldUri.fsPath} to ${newUri.fsPath}.`,
                    innerError: err,
                    severity: ERROR_SEVERITY.MINOR,
                }),
            };
        }
    }
}
//# sourceMappingURL=NodeJSFileStore.js.map