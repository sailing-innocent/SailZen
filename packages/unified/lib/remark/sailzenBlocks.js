import { SailASTTypes } from "../types";
/**
 * Remark plugin for SailZen block-level directives.
 *
 * Handles ::theorem, ::lemma, ::corollary, ::proposition, ::definition,
 * ::remark, ::proof, ::algorithm, ::table, and ::if-format[format] ... ::end.
 *
 * These directives are parsed from paragraph nodes at the AST level:
 * the opening directive must be the sole content of a paragraph (or start it),
 * and ::end must be the sole content of a terminating paragraph.
 */
// Match ::name[title]{opts} at start of a paragraph
const BLOCK_DIRECTIVE_REGEX = /^::(theorem|lemma|corollary|proposition|definition|remark|proof|algorithm|table|if-format)(?:\[([^\]]*)\])?(?:\s*\{([^}]*)\})?/;
const END_DIRECTIVE_REGEX = /^::end\s*$/;
function parseOptions(raw) {
    const options = {};
    if (!raw)
        return options;
    const regex = /\s*([^\s=:]+)\s*[=:]\s*(?:"([^"]*)"|'([^']*)'|([^\s,}]*))/g;
    let match;
    while ((match = regex.exec(raw)) !== null) {
        const key = match[1].trim();
        const value = match[2] || match[3] || match[4];
        if (key)
            options[key] = value;
    }
    return options;
}
function matchBlockDirective(node) {
    if (node.type !== "paragraph")
        return null;
    const para = node;
    if (!para.children || para.children.length === 0)
        return null;
    const first = para.children[0];
    if (first.type !== "text")
        return null;
    const m = first.value.match(BLOCK_DIRECTIVE_REGEX);
    if (!m)
        return null;
    // Allow trailing whitespace-only children after the directive.
    // If there is non-whitespace text on the same line, treat it as a normal paragraph.
    if (para.children.length > 1) {
        const rest = para.children.slice(1);
        const restText = rest
            .map((c) => c.value || "")
            .join("")
            .trim();
        if (restText)
            return null;
    }
    // Also check if there's trailing non-whitespace text in the first text node after the match
    const remaining = first.value.slice(m[0].length).trim();
    if (remaining)
        return null;
    return {
        type: m[1],
        title: m[2] || "",
        optionsRaw: m[3] || "",
    };
}
function isEndDirective(node) {
    if (node.type !== "paragraph")
        return false;
    const para = node;
    if (!para.children || para.children.length === 0)
        return false;
    const child = para.children[0];
    if (child.type !== "text")
        return false;
    return END_DIRECTIVE_REGEX.test(child.value);
}
function processChildren(parent) {
    if (!parent.children || parent.children.length === 0)
        return;
    const newChildren = [];
    const children = parent.children;
    let i = 0;
    while (i < children.length) {
        const directive = matchBlockDirective(children[i]);
        if (directive) {
            const contentNodes = [];
            let j = i + 1;
            while (j < children.length && !isEndDirective(children[j])) {
                contentNodes.push(children[j]);
                j++;
            }
            const endFound = j < children.length;
            j = endFound ? j + 1 : j;
            const options = parseOptions(directive.optionsRaw);
            let node;
            if (directive.type === "table") {
                const tableNode = contentNodes.length > 0 && contentNodes[0].type === "table"
                    ? contentNodes[0]
                    : undefined;
                node = {
                    type: SailASTTypes.SAILZEN_TABLE,
                    caption: directive.title,
                    label: options.label || "",
                    options,
                    table: tableNode,
                    children: tableNode ? contentNodes.slice(1) : contentNodes,
                };
            }
            else if (directive.type === "if-format") {
                node = {
                    type: SailASTTypes.SAILZEN_IF_FORMAT,
                    format: directive.title,
                    children: contentNodes,
                };
            }
            else if (directive.type === "algorithm") {
                node = {
                    type: SailASTTypes.SAILZEN_ALGORITHM,
                    title: directive.title,
                    label: options.label || "",
                    children: contentNodes,
                };
            }
            else {
                node = {
                    type: SailASTTypes.SAILZEN_MATH_ENV,
                    envType: directive.type,
                    title: directive.title || undefined,
                    label: options.label || undefined,
                    children: contentNodes,
                };
            }
            newChildren.push(node);
            i = j;
        }
        else {
            newChildren.push(children[i]);
            i++;
        }
    }
    parent.children = newChildren;
    // Recursively process any remaining containers
    for (const child of parent.children) {
        if (child &&
            typeof child === "object" &&
            "children" in child &&
            Array.isArray(child.children)) {
            processChildren(child);
        }
    }
}
const plugin = function (_opts) {
    return (tree) => {
        processChildren(tree);
    };
};
export { plugin as sailzenBlocks };
//# sourceMappingURL=sailzenBlocks.js.map