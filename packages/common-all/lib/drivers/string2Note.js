import matter from "gray-matter";
import YAML from "js-yaml";
import _ from "lodash";
import { DNodeUtils } from "../dnode";
import { DNodeImplicitPropsEnum } from "../types";
import { genHash } from "../utils";
/**
 * Shared note parsing helper used by server-side file utilities.
 * @param calculateHash - when set, add `contentHash` property to the note
 *  Default: false
 * @returns
 */
export function string2Note({ content, fname, vault, calculateHash, }) {
    const options = {
        engines: {
            yaml: {
                parse: (s) => YAML.load(s),
                stringify: (s) => YAML.dump(s),
            },
        },
    };
    const { data, content: body } = matter(content, options);
    if (data?.title)
        data.title = _.toString(data.title);
    if (data?.id)
        data.id = _.toString(data.id);
    const custom = DNodeUtils.getCustomProps(data);
    const contentHash = calculateHash ? genHash(content) : undefined;
    const note = DNodeUtils.create({
        ..._.omit(data, Object.values(DNodeImplicitPropsEnum)),
        custom,
        fname,
        body,
        type: "note",
        vault,
        contentHash,
    });
    return note;
}
//# sourceMappingURL=string2Note.js.map