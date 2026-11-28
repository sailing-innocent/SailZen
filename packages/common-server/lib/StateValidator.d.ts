import { DEngineClient, RespV3 } from "@saili/common-all";
/**
 * Validate correctness of engine notes compared with filesystem.
 * Currently supports parent/children relationship between notes
 */
export declare class StateValidator {
    static validateEngineState(engine: DEngineClient): Promise<RespV3<void>[]>;
}
