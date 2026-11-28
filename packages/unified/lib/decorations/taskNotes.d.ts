import { SailConfig, ReducedDEngine, VSRange } from "@saili/common-all";
import { Decoration, DECORATION_TYPES } from "./utils";
export type DecorationTaskNote = Decoration & {
    type: DECORATION_TYPES.taskNote;
    beforeText?: string;
    afterText?: string;
};
/** Decorates the note `fname` in vault `vaultName` if the note is a task note. */
export declare function decorateTaskNote({ engine, range, fname, vaultName, config, }: {
    engine: ReducedDEngine;
    range: VSRange;
    fname: string;
    vaultName?: string;
    config: SailConfig;
}): Promise<DecorationTaskNote | undefined>;
