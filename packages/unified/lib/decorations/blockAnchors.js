import { position2VSCodeRange } from "@saili/common-all";
import { DECORATION_TYPES } from "./utils";
export const decorateBlockAnchor = (opts) => {
    const { node: blockAnchor } = opts;
    const { position } = blockAnchor;
    const decoration = {
        type: DECORATION_TYPES.blockAnchor,
        range: position2VSCodeRange(position),
    };
    return {
        decorations: [decoration],
        errors: [],
    };
};
//# sourceMappingURL=blockAnchors.js.map