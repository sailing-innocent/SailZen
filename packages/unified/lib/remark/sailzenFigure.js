import { SailError } from "@saili/common-all";
import { SailASTDest, SailASTTypes } from "../types";
import { MDUtilsV5 } from "..";
/**
 * Remark plugin for SailZen ::figure[caption](src){opts} directive.
 *
 * Parses inline figures like:
 *   ::figure[Overview](fig_overview){width=0.8\textwidth}
 *   ::figure[Caption](image.png)
 *
 * And produces a sailzenFigure AST node.
 */
export const FIGURE_REGEX = /^::figure\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?/;
// Character codes
const codes = {
    colon: 58,
    f: 102,
    i: 105,
    g: 103,
    u: 117,
    r: 114,
    e: 101,
    openBracket: 91,
    closeBracket: 93,
    openParen: 40,
    closeParen: 41,
    openBrace: 123,
    closeBrace: 125,
};
/**
 * Simple key="value" or key=value parser
 */
function parseOptions(raw) {
    const options = {};
    if (!raw)
        return options;
    const regex = /\s*([^\s=]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s,}]*))/g;
    let match;
    while ((match = regex.exec(raw)) !== null) {
        const key = match[1].trim();
        const value = match[2] || match[3] || match[4];
        if (key) {
            options[key] = value;
        }
    }
    return options;
}
/**
 * Micromark syntax extension for ::figure[caption](src){opts}
 */
function createSailzenFigureSyntax() {
    const tokenizeSailzenFigure = function (effects, ok, nok) {
        return start;
        function start(code) {
            if (code !== codes.colon)
                return nok(code);
            effects.enter("sailzenFigure");
            effects.enter("sailzenFigureMarker");
            effects.consume(code);
            return secondColon;
        }
        function secondColon(code) {
            if (code !== codes.colon)
                return nok(code);
            effects.consume(code);
            effects.exit("sailzenFigureMarker");
            effects.enter("sailzenFigureKeyword");
            return keywordF;
        }
        function keywordF(code) {
            if (code !== codes.f)
                return nok(code);
            effects.consume(code);
            return keywordI;
        }
        function keywordI(code) {
            if (code !== codes.i)
                return nok(code);
            effects.consume(code);
            return keywordG;
        }
        function keywordG(code) {
            if (code !== codes.g)
                return nok(code);
            effects.consume(code);
            return keywordU;
        }
        function keywordU(code) {
            if (code !== codes.u)
                return nok(code);
            effects.consume(code);
            return keywordR;
        }
        function keywordR(code) {
            if (code !== codes.r)
                return nok(code);
            effects.consume(code);
            return keywordE;
        }
        function keywordE(code) {
            if (code !== codes.e)
                return nok(code);
            effects.consume(code);
            effects.exit("sailzenFigureKeyword");
            return openBracket;
        }
        function openBracket(code) {
            if (code !== codes.openBracket)
                return nok(code);
            effects.consume(code);
            effects.enter("sailzenFigureCaption");
            return insideCaption;
        }
        function insideCaption(code) {
            if (code === null)
                return nok(code);
            if (code === codes.closeBracket) {
                effects.exit("sailzenFigureCaption");
                effects.consume(code);
                return openParen;
            }
            effects.consume(code);
            return insideCaption;
        }
        function openParen(code) {
            if (code !== codes.openParen)
                return nok(code);
            effects.consume(code);
            effects.enter("sailzenFigureSrc");
            return insideSrc;
        }
        function insideSrc(code) {
            if (code === null)
                return nok(code);
            if (code === codes.closeParen) {
                effects.exit("sailzenFigureSrc");
                effects.consume(code);
                return optionalBrace;
            }
            effects.consume(code);
            return insideSrc;
        }
        function optionalBrace(code) {
            if (code === codes.openBrace) {
                effects.consume(code);
                effects.enter("sailzenFigureOptions");
                return insideOptions;
            }
            effects.exit("sailzenFigure");
            return ok(code);
        }
        function insideOptions(code) {
            if (code === null)
                return nok(code);
            if (code === codes.closeBrace) {
                effects.exit("sailzenFigureOptions");
                effects.consume(code);
                effects.exit("sailzenFigure");
                return ok(code);
            }
            effects.consume(code);
            return insideOptions;
        }
    };
    return {
        text: {
            [codes.colon]: {
                tokenize: tokenizeSailzenFigure,
            },
        },
    };
}
/**
 * mdast-util-from-markdown extension
 * Converts micromark tokens to mdast nodes
 */
function createFromMarkdownExtension() {
    const enterSailzenFigure = function (token) {
        this.enter({
            type: SailASTTypes.SAILZEN_FIGURE,
            caption: "",
            src: "",
            options: {},
        }, token);
    };
    const exitSailzenFigureCaption = function (token) {
        const node = this.stack[this.stack.length - 1];
        node.caption = this.sliceSerialize(token).trim();
    };
    const exitSailzenFigureSrc = function (token) {
        const node = this.stack[this.stack.length - 1];
        node.src = this.sliceSerialize(token).trim();
    };
    const exitSailzenFigureOptions = function (token) {
        const node = this.stack[this.stack.length - 1];
        const optsRaw = this.sliceSerialize(token).trim();
        node.options = parseOptions(optsRaw);
    };
    const exitSailzenFigure = function (token) {
        this.exit(token);
    };
    return {
        enter: {
            sailzenFigure: enterSailzenFigure,
        },
        exit: {
            sailzenFigureCaption: exitSailzenFigureCaption,
            sailzenFigureSrc: exitSailzenFigureSrc,
            sailzenFigureOptions: exitSailzenFigureOptions,
            sailzenFigure: exitSailzenFigure,
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
    const handleSailzenFigure = function (node, _parent, _state, _info) {
        const figNode = node;
        const dest = getDest(proc);
        const { caption, src, options } = figNode;
        switch (dest) {
            case SailASTDest.MD_SAIL:
            case SailASTDest.MD_REGULAR: {
                const optsStr = options && Object.keys(options).length
                    ? "{" + Object.entries(options).map(([k, v]) => `${k}="${v}"`).join(", ") + "}"
                    : "";
                return `::figure[${caption}](${src})${optsStr}`;
            }
            case SailASTDest.HTML:
                return `<figure>\n  <img src="${src}" alt="${caption}" />\n  <figcaption>${caption}</figcaption>\n</figure>`;
            case SailASTDest.DOC_EXPORT:
                return `__FIGURE__[${src}|${caption}]`;
            case SailASTDest.DOC_PREVIEW:
                return `<figure class="sailzen-figure">\n  <div class="sailzen-figure-placeholder">📷 ${src}</div>\n  <figcaption>${caption}</figcaption>\n</figure>`;
            default:
                throw new SailError({
                    message: `Unable to render sailzenFigure for dest ${dest}`,
                });
        }
    };
    return {
        handlers: {
            [SailASTTypes.SAILZEN_FIGURE]: handleSailzenFigure,
        },
    };
}
const plugin = function (_opts) {
    const proc = this;
    const data = proc.data();
    // Add micromark syntax extension
    const micromarkExtensions = data.micromarkExtensions || [];
    micromarkExtensions.push(createSailzenFigureSyntax());
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
export { plugin as sailzenFigure };
//# sourceMappingURL=sailzenFigure.js.map