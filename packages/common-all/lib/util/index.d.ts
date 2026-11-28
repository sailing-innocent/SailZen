export { URI } from "vscode-uri";
export * from "./cache";
export * from "./compat";
export * from "./dateFormatUtil";
export * from "./orderedMatchter";
export * from "./regex";
export * from "./responseUtil";
export * from "./stringUtil";
export * from "./treeUtil";
/**
 * Defaultdict from Python
 */
export declare class DefaultMap<K = string, V = any> extends Map<K, V> {
    private defaultMethod;
    get(key: K): V;
    constructor(defaultMethod: () => V);
}
