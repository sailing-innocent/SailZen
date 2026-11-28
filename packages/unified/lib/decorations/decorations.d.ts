import { SailError, DEngine, Diagnostic, GetDecorationsOpts, ISailError, SailConfig, NoteProps } from "@saili/common-all";
import { Decoration } from "./utils";
/** Get all decorations within the visible ranges for given note. */
export declare function runAllDecorators(opts: Omit<GetDecorationsOpts, "id"> & {
    note: NoteProps;
    engine: DEngine;
    config: SailConfig;
}): Promise<{
    errors: SailError<import("@saili/common-all").StatusCodes | undefined>[];
    allDecorations?: undefined;
    allDiagnostics?: undefined;
    allErrors?: undefined;
} | {
    allDecorations: Decoration[];
    allDiagnostics: Diagnostic[];
    allErrors: ISailError[];
    errors?: undefined;
}>;
