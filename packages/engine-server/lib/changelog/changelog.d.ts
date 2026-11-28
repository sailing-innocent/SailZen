import { DEngineClient } from "@saili/common-all";
export declare class ChangelogGenerator {
    static getChangelogDataPath(wsRoot: string): string;
}
/**
 * Gets list of notes that were changed + commit hash and save it to file in build/ dir.
 */
export declare function generateChangelog(engine: DEngineClient): Promise<void>;
