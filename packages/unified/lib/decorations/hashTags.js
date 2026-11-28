import { ConfigUtils, NoteUtils, position2VSCodeRange, } from "@saili/common-all";
import { linkedNoteType } from "./wikilinks";
export function isDecorationHashTag(decoration) {
    return decoration.color !== undefined;
}
export const decorateHashTag = (opts) => {
    const { node: hashtag, engine, config, note } = opts;
    const { position } = hashtag;
    return decorateTag({
        fname: hashtag.fname,
        engine,
        position,
        config,
        note,
    });
};
export async function decorateTag({ fname, engine, position, lineOffset, config, note, }) {
    let color;
    const { color: foundColor, type: colorType } = NoteUtils.color({
        fname,
        note,
        // engine,
    });
    const enableRandomlyColoredTags = ConfigUtils.getPublishing(config).enableRandomlyColoredTags;
    if (colorType === "configured" || enableRandomlyColoredTags) {
        color = foundColor;
    }
    const { type, errors } = await linkedNoteType({
        fname,
        engine,
        vaults: config.workspace?.vaults ?? [],
    });
    const decoration = {
        type,
        range: position2VSCodeRange(position, { line: lineOffset }),
        color,
    };
    return { errors, decorations: [decoration] };
}
//# sourceMappingURL=hashTags.js.map