import { genUUID, NoteUtils, } from "@saili/common-all";
import _ from "lodash";
export class BackfillService {
    async updateNotes(opts) {
        const { engine, note, overwriteFields } = _.defaults(opts, {
            overwriteFields: [],
        });
        const candidates = _.isUndefined(note)
            ? await engine.findNotes({ excludeStub: true })
            : [note];
        const notes = await Promise.all(candidates
            .filter((n) => !n.stub)
            .map(async (n) => {
            overwriteFields.forEach((f) => {
                if (f === "title") {
                    n.title = NoteUtils.genTitle(n.fname);
                }
                else if (f === "id") {
                    // ids starting or ending with `-` or `_` break pages in Github publishing
                    if (n.id.match(/^[-_]|[-_]$/)) {
                        n.id = genUUID();
                    }
                }
                else {
                    throw Error(`unknown overwrite field: ${f}`);
                }
            });
            return n;
        }));
        await engine.bulkWriteNotes({ notes, opts: { overrideExisting: true } });
        return {};
    }
}
//# sourceMappingURL=service.js.map