import { sort as sortPaths } from "cross-path-sort";
import { URI } from "vscode-uri";
import { RefT, WorkspaceCache } from "../types";
export { sortPaths };
export declare const REGEX_FENCED_CODE_BLOCK: RegExp;
export declare const containsMarkdownExt: (pathParam: string) => boolean;
export declare const refPattern = "(\\[\\[)([^\\[\\]]+?)(\\]\\])";
export declare const findUriByRef: (uris: URI[], ref: string) => URI | undefined;
export declare const lineBreakOffsetsByLineIndex: (value: string) => number[];
export declare const positionToOffset: (content: string, position: {
    line: number;
    column: number;
}) => number;
export declare const getFileUrlForMarkdownPreview: (filePath: string) => string;
export declare const isInFencedCodeBlock: (content: string, lineNum: number) => boolean;
export declare const trimLeadingSlash: (value: string) => string;
export declare const normalizeSlashes: (value: string) => string;
export declare const fsPathToRef: ({ path: fsPath, keepExt, basePath, }: {
    path: string;
    keepExt?: boolean;
    basePath?: string;
}) => string | null;
export declare const parseRef: (rawRef: string) => RefT;
export declare const extractDanglingRefs: (content: string) => string[];
export declare const getWorkspaceCache: () => WorkspaceCache;
export declare const matchAll: (pattern: RegExp, text: string) => Array<RegExpMatchArray>;
