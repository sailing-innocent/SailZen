import { position2VSCodeRange, } from "@saili/common-all";
import { linkedNoteType } from "./wikilinks";
export const decorateZDocTag = async (opts) => {
    const { node: zdocTag, engine, config } = opts;
    const position = zdocTag.position;
    const { type, errors } = await linkedNoteType({
        fname: zdocTag.fname,
        engine,
        vaults: config.workspace?.vaults ?? [],
    });
    const decoration = {
        type,
        range: position2VSCodeRange(position),
    };
    return {
        decorations: [decoration],
        errors,
    };
};
//# sourceMappingURL=zdocTags.js.map