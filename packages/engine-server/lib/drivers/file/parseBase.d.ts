import { DStore } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
export declare class ParserBase {
    opts: {
        store: DStore;
        logger: DLogger;
    };
    constructor(opts: {
        store: DStore;
        logger: DLogger;
    });
    get logger(): DLogger;
}
