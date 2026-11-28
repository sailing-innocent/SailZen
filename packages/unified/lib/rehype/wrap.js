import { visit } from "unist-util-visit";
// @ts-ignore
import parseSelector from "hast-util-parse-selector";
// @ts-ignore
import { selectAll } from "hast-util-select";
const plugin = function plugin(opts) {
    function transformer(tree) {
        const root = tree;
        for (const match of selectAll(opts.selector, root)) {
            const wrapper = parseSelector(opts.wrapper);
            visit(tree, match, (node, i, parent) => {
                wrapper.children = [node];
                if (parent) {
                    parent.children[i] = wrapper;
                }
            });
        }
    }
    return transformer;
};
export { plugin as wrap };
//# sourceMappingURL=wrap.js.map