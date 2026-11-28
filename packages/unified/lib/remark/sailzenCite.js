import { SailError } from "@saili/common-all";
import { SailASTDest, SailASTTypes } from "../types";
import { MDUtilsV5 } from "..";
/**
 * Remark plugin for SailZen ::cite[keys] directive.
 *
 * Parses inline citations like:
 *   ::cite[foo, bar]
 *   ::cite[ foo , bar ]
 *
 * And produces a sailzenCite AST node.
 */
export const CITE_REGEX = /^::cite\[([^\]]*)\]/;
// Character codes
const codes = {
    colon: 58,
    c: 99,
    i: 105,
    t: 116,
    e: 101,
    openBracket: 91,
    closeBracket: 93,
};
/**
 * Micromark syntax extension for ::cite[keys]
 */
function createSailzenCiteSyntax() {
    const tokenizeSailzenCite = function (effects, ok, nok) {
        return start;
        function start(code) {
            if (code !== codes.colon)
                return nok(code);
            effects.enter("sailzenCite");
            effects.enter("sailzenCiteMarker");
            effects.consume(code);
            return secondColon;
        }
        function secondColon(code) {
            if (code !== codes.colon)
                return nok(code);
            effects.consume(code);
            effects.exit("sailzenCiteMarker");
            effects.enter("sailzenCiteKeyword");
            return keywordC;
        }
        function keywordC(code) {
            if (code !== codes.c)
                return nok(code);
            effects.consume(code);
            return keywordI;
        }
        function keywordI(code) {
            if (code !== codes.i)
                return nok(code);
            effects.consume(code);
            return keywordT;
        }
        function keywordT(code) {
            if (code !== codes.t)
                return nok(code);
            effects.consume(code);
            return keywordE;
        }
        function keywordE(code) {
            if (code !== codes.e)
                return nok(code);
            effects.consume(code);
            effects.exit("sailzenCiteKeyword");
            return openBracket;
        }
        function openBracket(code) {
            if (code !== codes.openBracket)
                return nok(code);
            effects.consume(code);
            effects.enter("sailzenCiteContent");
            return insideContent;
        }
        function insideContent(code) {
            if (code === null || code === codes.closeBracket) {
                effects.exit("sailzenCiteContent");
                return closeBracket;
            }
            effects.consume(code);
            return insideContent;
        }
        function closeBracket(code) {
            if (code !== codes.closeBracket)
                return nok(code);
            effects.consume(code);
            effects.exit("sailzenCite");
            return ok(code);
        }
    };
    return {
        text: {
            [codes.colon]: {
                tokenize: tokenizeSailzenCite,
            },
        },
    };
}
/**
 * mdast-util-from-markdown extension
 * Converts micromark tokens to mdast nodes
 */
function createFromMarkdownExtension() {
    const enterSailzenCite = function (token) {
        this.enter({
            type: SailASTTypes.SAILZEN_CITE,
            keys: [],
        }, token);
    };
    const exitSailzenCiteContent = function (token) {
        const content = this.sliceSerialize(token);
        const node = this.stack[this.stack.length - 1];
        node.keys = content
            .split(/,\s*/)
            .map((s) => s.trim())
            .filter(Boolean);
    };
    const exitSailzenCite = function (token) {
        this.exit(token);
    };
    return {
        enter: {
            sailzenCite: enterSailzenCite,
        },
        exit: {
            sailzenCiteContent: exitSailzenCiteContent,
            sailzenCite: exitSailzenCite,
        },
    };
}
function getDest(proc) {
    const procData = MDUtilsV5.getProcData(proc);
    if (procData.dest)
        return procData.dest;
    const directDest = proc.data().dest;
    if (directDest)
        return directDest;
    return SailASTDest.MD_SAIL;
}
/**
 * mdast-util-to-markdown extension
 * Converts mdast nodes back to markdown
 */
function createToMarkdownExtension(proc) {
    const handleSailzenCite = function (node, _parent, _state, _info) {
        const citeNode = node;
        const dest = getDest(proc);
        const keys = citeNode.keys.join(", ");
        switch (dest) {
            case SailASTDest.MD_SAIL:
            case SailASTDest.MD_REGULAR:
                return `::cite[${keys}]`;
            case SailASTDest.HTML:
                return `<sup>[${keys}]</sup>`;
            case SailASTDest.DOC_EXPORT:
                return `__CITE__[${keys}]`;
            case SailASTDest.DOC_PREVIEW:
                return `<sup class="sailzen-cite">[${keys}]</sup>`;
            default:
                throw new SailError({
                    message: `Unable to render sailzenCite for dest ${dest}`,
                });
        }
    };
    return {
        handlers: {
            [SailASTTypes.SAILZEN_CITE]: handleSailzenCite,
        },
    };
}
const plugin = function (_opts) {
    const proc = this;
    const data = proc.data();
    // Add micromark syntax extension
    const micromarkExtensions = data.micromarkExtensions || [];
    micromarkExtensions.push(createSailzenCiteSyntax());
    data.micromarkExtensions = micromarkExtensions;
    // Add fromMarkdown extension
    const fromMarkdownExtensions = data.fromMarkdownExtensions || [];
    fromMarkdownExtensions.push(createFromMarkdownExtension());
    data.fromMarkdownExtensions = fromMarkdownExtensions;
    // Add toMarkdown extension (for stringification)
    const toMarkdownExtensions = data.toMarkdownExtensions || [];
    toMarkdownExtensions.push(createToMarkdownExtension(proc));
    data.toMarkdownExtensions = toMarkdownExtensions;
};
export { plugin as sailzenCite };
//# sourceMappingURL=sailzenCite.js.map