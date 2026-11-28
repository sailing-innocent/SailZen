import { Diagnostic, ISailError, NoteProps } from "@saili/common-all";
import { FrontmatterContent } from "mdast";
export declare const BAD_FRONTMATTER_CODE = "bad frontmatter";
export declare const NOT_A_STUB = "not a stub";
export declare function warnMissingFrontmatter(): Diagnostic;
export declare function checkAndWarnBadFrontmatter(note: NoteProps, frontmatter: FrontmatterContent): {
    diagnostics: Diagnostic[];
    errors: ISailError[];
};
