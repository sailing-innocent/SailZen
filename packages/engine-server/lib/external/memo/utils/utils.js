/* eslint-disable no-cond-assign */
/* eslint-disable no-restricted-syntax */
/* eslint-disable no-use-before-define */
import { sort as sortPaths } from "cross-path-sort";
import _ from "lodash";
import path from "path";
import { URI } from "vscode-uri";
export { sortPaths };
const workspaceCache = {
    imageUris: [],
    markdownUris: [],
    otherUris: [],
    allUris: [],
    danglingRefsByFsPath: {},
    danglingRefs: [],
};
const markdownExtRegex = /\.md$/i;
export const REGEX_FENCED_CODE_BLOCK = /^( {0,3}|\t)```[^`\r\n]*$[\w\W]+?^( {0,3}|\t)``` *$/gm;
export const containsMarkdownExt = (pathParam) => !!markdownExtRegex.exec(path.parse(pathParam).ext);
export const refPattern = "(\\[\\[)([^\\[\\]]+?)(\\]\\])";
// === Utils
export const findUriByRef = (uris, ref) => {
    return uris.find((uri) => {
        // const relativeFsPath =
        //   path.sep + path.relative(getWorkspaceFolder()!.toLowerCase(), uri.fsPath.toLowerCase());
        // if (containsImageExt(ref) || containsOtherKnownExts(ref) || containsUnknownExt(ref)) {
        //   if (isLongRef(ref)) {
        //     return normalizeSlashes(relativeFsPath).endsWith(ref.toLowerCase());
        //   }
        //   const basenameLowerCased = path.basename(uri.fsPath).toLowerCase();
        //   return (
        //     basenameLowerCased === ref.toLowerCase() || basenameLowerCased === `${ref.toLowerCase()}.md`
        //   );
        // }
        // if (isLongRef(ref)) {
        //   return normalizeSlashes(relativeFsPath).endsWith(`${ref.toLowerCase()}.md`);
        // }
        const name = path.parse(uri.fsPath).name.toLowerCase();
        return (containsMarkdownExt(path.basename(uri.fsPath)) &&
            name === ref.toLowerCase());
    });
};
export const lineBreakOffsetsByLineIndex = (value) => {
    const result = [];
    let index = value.indexOf("\n");
    while (index !== -1) {
        result.push(index + 1);
        index = value.indexOf("\n", index + 1);
    }
    result.push(value.length + 1);
    return result;
};
export const positionToOffset = (content, position) => {
    if (position.line < 0) {
        throw new Error("Illegal argument: line must be non-negative");
    }
    if (position.column < 0) {
        throw new Error("Illegal argument: column must be non-negative");
    }
    const lineBreakOffsetsByIndex = lineBreakOffsetsByLineIndex(content);
    if (lineBreakOffsetsByIndex[position.line] !== undefined) {
        return ((lineBreakOffsetsByIndex[position.line - 1] || 0) + position.column || 0);
    }
    return 0;
};
export const getFileUrlForMarkdownPreview = (filePath) => URI.file(filePath).toString().replace("file://", "");
export const isInFencedCodeBlock = (content, lineNum) => {
    const textBefore = content
        .slice(0, positionToOffset(content, { line: lineNum, column: 0 }))
        .replace(REGEX_FENCED_CODE_BLOCK, "")
        .replace(/<!--[\W\w]+?-->/g, "");
    // So far `textBefore` should contain no valid fenced code block or comment
    return /^( {0,3}|\t)```[^`\r\n]*$[\w\W]*$/gm.test(textBefore);
};
export const trimLeadingSlash = (value) => value.replace(/^\/+|^\\+/g, "");
export const normalizeSlashes = (value) => value.replace(/\\/gi, "/");
export const fsPathToRef = ({ path: fsPath, keepExt, basePath, }) => {
    const ref = basePath && fsPath.startsWith(basePath)
        ? normalizeSlashes(fsPath.replace(basePath, ""))
        : path.basename(fsPath);
    if (keepExt) {
        return trimLeadingSlash(ref);
    }
    return trimLeadingSlash(ref.includes(".") ? ref.slice(0, ref.lastIndexOf(".")) : ref);
};
export const parseRef = (rawRef) => {
    const dividerPosition = rawRef.indexOf("|");
    if (dividerPosition < 0) {
        return {
            ref: _.trim(rawRef),
            label: _.trim(rawRef),
        };
    }
    else {
        return {
            ref: _.trim(rawRef.slice(dividerPosition + 1, rawRef.length)),
            label: _.trim(rawRef.slice(0, dividerPosition)),
        };
    }
};
const refRegexp = new RegExp(refPattern, "gi");
export const extractDanglingRefs = (content) => {
    const refs = [];
    content.split(/\r?\n/g).forEach((lineText, _lineNum) => {
        for (const match of matchAll(refRegexp, lineText)) {
            const [, , reference] = match;
            if (reference) {
                // const offset = (match.index || 0) + 2;
                // if (isInFencedCodeBlock(content, lineNum) || isInCodeSpan(content, lineNum, offset)) {
                //   continue;
                // }
                const { ref } = parseRef(reference);
                if (!findUriByRef(getWorkspaceCache().allUris, ref)) {
                    refs.push(ref);
                }
            }
        }
    });
    return Array.from(new Set(refs));
};
export const getWorkspaceCache = () => workspaceCache;
export const matchAll = (pattern, text) => {
    let match;
    const out = [];
    pattern.lastIndex = 0;
    while ((match = pattern.exec(text))) {
        out.push(match);
    }
    return out;
};
//# sourceMappingURL=utils.js.map