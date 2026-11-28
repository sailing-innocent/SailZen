import { parse as yamlparse, } from "yaml-unist-parser";
import _ from "lodash";
export function isYamlUnistParent(node) {
    return _.isArray(node?.children);
}
export function isMappingItem(node) {
    return node?.type === "mappingItem";
}
export function isPlain(node) {
    return node?.type === "plain";
}
export function isQuoteSingle(node) {
    return node?.type === "quoteSingle";
}
export function isQuoteDouble(node) {
    return node?.type === "quoteDouble";
}
export function isYamlString(node) {
    return isPlain(node) || isQuoteSingle(node) || isQuoteDouble(node);
}
/** `unist-util-visit`, kind of, but for YamlUnist.
 *
 * The reason this is duplicated here is that even though YamlUnist is
 * technically Unist compatible, the types don't match so we can't use the unist
 * function.
 */
export function visitYamlUnist(node, visitor) {
    const toVisit = _.isArray(node) ? [...node] : [node];
    while (toVisit.length > 0) {
        const item = toVisit.pop();
        if (_.isUndefined(item))
            return;
        const out = visitor(item);
        if (out === false)
            return;
        if (isYamlUnistParent(item)) {
            toVisit.push(...item.children);
        }
    }
}
/** Get the mapping items (`key: value`) from the frontmatter. */
export function parseFrontmatter(frontmatter) {
    const parsed = yamlparse(_.isString(frontmatter) ? frontmatter : frontmatter.value);
    const mapping = parsed.children[0]?.children[1]?.children[0]
        ?.children;
    return mapping;
}
export function getFrontmatterTags(frontmatter) {
    const tags = [];
    visitYamlUnist(frontmatter, (node) => {
        if (!isMappingItem(node))
            return;
        const [key, value] = node.children;
        let isTags = false;
        visitYamlUnist(key, (keyPlain) => {
            if (!isYamlString(keyPlain))
                return;
            if (keyPlain.value === "tags") {
                isTags = true;
                return false; // stop traversal
            }
            return;
        });
        if (!isTags)
            return;
        visitYamlUnist(value, (valuePlain) => {
            if (!isYamlString(valuePlain))
                return;
            tags.push(valuePlain);
            return;
        });
        return;
    });
    return tags;
}
//# sourceMappingURL=yaml.js.map