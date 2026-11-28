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
export class DefaultMap extends Map {
    defaultMethod;
    get(key) {
        if (!this.has(key)) {
            this.set(key, this.defaultMethod());
        }
        return super.get(key);
    }
    constructor(defaultMethod) {
        super();
        this.defaultMethod = defaultMethod;
    }
}
//# sourceMappingURL=index.js.map