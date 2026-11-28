import { MigrationChangeSetStatus } from "./types";
type mappedConfigPath = {
    /**
     * legacy config path to target.
     */
    target: string;
    /**
     * How we want to map the config.
     * if "skip", don't map.
     *   use this when it is a namespace that itself has properties.
     * if undefined, identity mapping is assumed (_.identity)
     */
    iteratee?: Function | "skip";
    /**
     * Set to true to mark that legacy path should be preserved.
     */
    preserve?: boolean;
};
/**
 * map of new config's path to old config's path and how it should be mapped.
 * e.g.
 *    "commands.lookup" is a new config path, that was originally at "lookup".
 *    This mapping should be skipped during migration.
 *
 *    "commands.lookup.note.selectionMode" is a new config path
 *    that was originally "lookup.note.selectionType".
 *    This mapping should be done by _iteratee_, which maps to the new enums.
 *
 * only paths that strictly have a mapping is present.
 * newly introduced namespace path (i.e. "commands", or "workspace") is not here
 * because they don't have a mapping to the old version.
 */
export declare const PATH_MAP: Map<string, mappedConfigPath>;
/** ^2hgqigv11pvy
 * List of config paths that are deprecated
 * and should be checked for existence
 * and deleted from `sail.yml`
 */
export declare const DEPRECATED_PATHS: string[];
export declare class MigrationUtils {
    /**
     * clean up an object recursively with given predicate.
     * @param obj a plain object
     * @param pred predicate to use for recursively omitting
     * @returns obj, with properties omitted by pred
     */
    static deepCleanObjBy(obj: any, pred: Function): any;
    static getMigrationAnalyticProps({ data: { changeName, status, version }, }: MigrationChangeSetStatus): {
        data: {
            changeName: string;
            status: "error" | "ok";
            version: string;
        };
    };
}
export {};
