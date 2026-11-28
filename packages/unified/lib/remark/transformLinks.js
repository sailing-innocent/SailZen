import { visit } from "unist-util-visit";
import { SailASTTypes } from "../types";
/**
 * Used from renaming wikilinks
 */
function plugin(opts) {
    // @ts-ignore
    const proc = this;
    function transformer(tree, _file) {
        visit(tree, (node, _idx, _parent) => {
            if (node.type === SailASTTypes.WIKI_LINK) {
                let cnode = node;
                if (cnode.value.toLowerCase() === opts.from.fname.toLowerCase()) {
                    cnode.value = opts.to.fname;
                    // if alias the same, change that to
                    if (cnode.data.alias.toLowerCase() === opts.from.fname.toLowerCase()) {
                        cnode.data.alias = opts.to.fname;
                    }
                }
            }
            if (node.type === SailASTTypes.REF_LINK_V2) {
                let cnode = node;
                if (cnode.data.link.from.fname.toLowerCase() ===
                    opts.from.fname.toLowerCase()) {
                    cnode.data.link.from.fname = opts.to.fname;
                }
            }
        });
        return tree;
    }
    return transformer;
}
export { plugin as transformLinks };
//# sourceMappingURL=transformLinks.js.map