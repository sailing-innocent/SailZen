import { visit } from "unist-util-visit";
import { SailASTDest, SailASTTypes } from "../types";
import { PublishUtils } from "../utils";
import { MDUtilsV5 } from "../utilsv5";
/**
 * Used when publishing
 * Rewrite index note
 */
function plugin(opts) {
    const proc = this;
    const { dest, config } = MDUtilsV5.getProcData(proc);
    function transformer(tree, _file) {
        if (dest !== SailASTDest.HTML) {
            return;
        }
        visit(tree, (node, _idx, _parent) => {
            if (node.type === SailASTTypes.WIKI_LINK) {
                const cnode = node;
                const value = cnode.value;
                const href = PublishUtils.getSiteUrl(config);
                if (value === opts.noteIndex.fname) {
                    node.data.hProperties = { href };
                }
            }
        });
        return tree;
    }
    return transformer;
}
export { plugin as publishSite };
//# sourceMappingURL=publishSite.js.map