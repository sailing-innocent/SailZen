import _ from "lodash";
import { SailError } from "@saili/common-all";
import { SailASTDest, SailASTTypes } from "../types";
import { html } from "mdast-builder";
import YAML from "js-yaml";
import { MDUtilsV5 } from "../utilsv5";
export const EXTENDED_IMAGE_REGEX = /^!\[(?<alt>[^[\]]*)\]\((?<url>.*)\)(?<props>{[^{}]*})/;
export const EXTENDED_IMAGE_REGEX_LOOSE = /!\[(?<alt>[^[\]]*)\]\((?<url>.*)\)(?<props>{[^{}]*})/;
export const matchExtendedImage = (text, matchLoose = true) => {
    const match = (matchLoose ? EXTENDED_IMAGE_REGEX_LOOSE : EXTENDED_IMAGE_REGEX).exec(text);
    if (match && match.groups?.url && match.groups)
        return match[1];
    return undefined;
};
const plugin = function (opts) {
    attachParser(this);
    if (this.Compiler != null) {
        attachCompiler(this, opts);
    }
};
function attachParser(proc) {
    function locator(value, fromIndex) {
        return value.indexOf("!", fromIndex);
    }
    function inlineTokenizer(eat, value) {
        const match = EXTENDED_IMAGE_REGEX.exec(value);
        if (match && match.groups?.url) {
            let props = {};
            try {
                props = YAML.load(match.groups.props);
            }
            catch {
                // Reject bad props so that it falls back to a regular image
                return;
            }
            return eat(match[0])({
                type: SailASTTypes.EXTENDED_IMAGE,
                // @ts-ignore
                value,
                url: match.groups.url,
                alt: match.groups.alt,
                props,
            });
        }
        return;
    }
    inlineTokenizer.locator = locator;
    const Parser = proc.Parser;
    if (!Parser)
        return;
    const inlineTokenizers = Parser.prototype.inlineTokenizers;
    const inlineMethods = Parser.prototype.inlineMethods;
    inlineTokenizers.extendedImage = inlineTokenizer;
    inlineMethods.splice(inlineMethods.indexOf("link"), 0, "extendedImage");
}
function attachCompiler(proc, _opts) {
    const Compiler = proc.Compiler;
    if (!Compiler)
        return;
    const visitors = Compiler.prototype.visitors;
    if (visitors) {
        visitors.extendedImage = function (node) {
            const { dest } = MDUtilsV5.getProcData(proc);
            const alt = node.alt ? node.alt : "";
            switch (dest) {
                case SailASTDest.MD_SAIL:
                    return `![${alt}](${node.url})${_.trim(YAML.dump(node.props, {
                        /* Inline-only so we get JSON style {foo: bar} */
                        flowLevel: 0,
                    }))}`;
                case SailASTDest.MD_REGULAR:
                    return `![${alt}](${node.url})`;
                case SailASTDest.MD_ENHANCED_PREVIEW:
                    return extendedImage2htmlRaw(node);
                default:
                    throw new SailError({
                        message: "Unable to render extended image",
                    });
            }
        };
    }
}
const ALLOWED_STYLE_PROPS = new Set([
    "width",
    "height",
    "float",
    "border",
    "margin",
    "padding",
    "min-width",
    "min-height",
    "max-width",
    "max-height",
    "display",
    "opacity",
    "outline",
    "rotate",
    "transition",
    "transform-origin",
    "transform",
    "z-index",
]);
export function extendedImage2htmlRaw(node, _opts) {
    const stylesList = [];
    const nodePropsList = [];
    for (const [prop, value] of Object.entries(node.props)) {
        if (ALLOWED_STYLE_PROPS.has(prop))
            stylesList.push(`${prop}:${value};`);
    }
    nodePropsList.push(`src="${node.url}"`);
    if (node.alt)
        nodePropsList.push(`alt="${node.alt}"`);
    return `<img ${nodePropsList.join(" ")} style="${stylesList.join("")}">`;
}
export function extendedImage2html(node, opts) {
    return html(extendedImage2htmlRaw(node, opts));
}
export { plugin as extendedImage };
//# sourceMappingURL=extendedImage.js.map