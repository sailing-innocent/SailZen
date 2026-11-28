import { isNotUndefined, NoteUtils, point2VSCodePosition, TAGS_HIERARCHY, } from "@saili/common-all";
import { decorateTag } from "./hashTags";
import { DECORATION_TYPES } from "./utils";
import _ from "lodash";
import { getFrontmatterTags, parseFrontmatter } from "../yaml";
export const decorateFrontmatter = async (opts) => {
    const { node: frontmatter, config, engine, note } = opts;
    const { value: contents, position } = frontmatter;
    // Decorate the timestamps
    const entries = contents.split("\n");
    const lineOffset = point2VSCodePosition(position.start).line +
        1; /* `---` line of frontmatter */
    const timestampDecorations = entries
        .map((entry, line) => {
        const match = NoteUtils.RE_FM_UPDATED_OR_CREATED.exec(entry);
        if (!_.isNull(match) && match.groups?.timestamp) {
            const timestamp = _.toInteger(match.groups.timestamp);
            const decoration = {
                range: {
                    start: {
                        line: line + lineOffset,
                        character: match.groups.beforeTimestamp.length,
                    },
                    end: {
                        line: line + lineOffset,
                        character: match.groups.beforeTimestamp.length +
                            match.groups.timestamp.length,
                    },
                },
                timestamp,
                type: DECORATION_TYPES.timestamp,
            };
            return decoration;
        }
        return undefined;
    })
        .filter(isNotUndefined);
    // Decorate the frontmatter tags
    const tags = getFrontmatterTags(parseFrontmatter(contents));
    const tagDecorations = [];
    const errors = [];
    await Promise.all(tags.map(async (tag) => {
        const { errors, decorations } = await decorateTag({
            fname: `${TAGS_HIERARCHY}${tag.value}`,
            position: tag.position,
            lineOffset,
            config,
            engine,
            note,
        });
        tagDecorations.push(...decorations);
        errors.push(...errors);
    }));
    const decorations = [
        ...tagDecorations,
        ...timestampDecorations,
    ];
    return {
        decorations,
        errors,
    };
};
//# sourceMappingURL=frontmatter.js.map