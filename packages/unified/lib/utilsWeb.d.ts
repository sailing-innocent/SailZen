import { ProcFlavor } from "@saili/common-all";
import { ProcDataFullOptsV5 } from "./utilsv5";
import { Processor } from "unified";
/**
 * Special version of MDUtilsV5 to get preview working in the web extension.
 * This class should eventually be deleted and converged with utilsV5 once
 * utilsV5 is compatible with EngineV3.
 */
export declare class MDUtilsV5Web {
    static procRehypeWeb(data: Omit<ProcDataFullOptsV5, "dest">, opts?: {
        flavor?: ProcFlavor;
    }): Processor<any>;
    /**
     * Used for processing a Sail markdown note
     */
    private static _procRemarkWeb;
    private static _procRehype;
    /**
     * Parse Sail Markdown Note. No compiler is attached.
     * @param opts
     * @param data
     * @returns
     */
    private static procRemarkParse;
}
