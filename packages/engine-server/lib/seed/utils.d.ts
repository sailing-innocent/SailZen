import { SailError, DVault, SeedConfig } from "@saili/common-all";
export declare class SeedUtils {
    static exists({ id, wsRoot }: {
        id: string;
        wsRoot: string;
    }): Promise<boolean>;
    static genDefaultConfig(opts: {
        id: string;
        seed?: SeedConfig;
        name: string;
    }): SeedConfig;
    static getSeedId({ publisher, name }: {
        publisher: string;
        name: string;
    }): string;
    /**
     * Path for seed
     * @param wsRoot - workspace root
     * @param id - id of seed
     * @returns
     */
    static seed2Path({ wsRoot, id }: {
        wsRoot: string;
        id: string;
    }): string;
    static seed2Vault({ seed }: {
        seed: SeedConfig;
    }): DVault;
    static validateWorkspaceSeedConversion({ wsRoot }: {
        wsRoot: string;
    }): {
        error: SailError<import("@saili/common-all").StatusCodes | undefined>;
    } | {
        error: undefined;
    };
}
