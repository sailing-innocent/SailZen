import { SailError, DVault, SchemaModuleProps } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
export declare class SchemaParser {
    private logger;
    private wsRoot;
    constructor({ wsRoot, logger }: {
        wsRoot: string;
        logger: DLogger;
    });
    private parseFile;
    parse(fpaths: string[], vault: DVault): Promise<{
        schemas: SchemaModuleProps[];
        errors: SailError[] | null;
    }>;
}
