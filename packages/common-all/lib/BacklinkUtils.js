import _ from "lodash";
import { DLinkUtils } from "./DLinkUtils";
export class BacklinkUtils {
    /**
     * Create backlink out of link if it references another note (denoted by presence of link.to field)
     *
     * @param link Original link to create backlink out of
     * @returns backlink or none if not applicable
     */
    static createFromDLink(link) {
        const maybeToNoteFname = link.to?.fname;
        if (maybeToNoteFname) {
            return {
                from: link.from,
                type: "backlink",
                position: link.position,
                value: link.value,
            };
        }
        return;
    }
    /** Adds a backlink by mutating the 'note' argument in place.
     * Check if backlink already exists before pushing
     *
     *  @param note note that the link is pointing to. (mutated)
     *  @param link backlink to add. */
    static addBacklinkInPlace({ note, backlink, }) {
        if (!note.links.some((linkToCompare) => DLinkUtils.isEquivalent(backlink, linkToCompare))) {
            note.links.push(backlink);
        }
    }
    /**
     * Remove backlink from note. If note does not contain that backlink, do nothing.
     * Mutates note in place
     *
     * @param note Note to update backlinks for.
     * @param backlink Backlink to remove
     */
    static removeBacklinkInPlace({ note, backlink, }) {
        const filteredBacklinks = note.links.filter((link) => {
            return !_.isEqual(backlink, link);
        });
        note.links = filteredBacklinks;
    }
}
//# sourceMappingURL=BacklinkUtils.js.map