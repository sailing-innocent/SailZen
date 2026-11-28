import { genDefaultCopyNoteLinkConfig } from ".";
import { genDefaultInsertNoteIndexConfig, } from "./insertNoteIndex";
import { genDefaultInsertNoteLinkConfig, } from "./insertNoteLink";
import { genDefaultLookupConfig } from "./lookup";
import { genDefaultRandomNoteConfig } from "./randomNote";
/**
 * Generates default {@link SailCommandConfig} using
 * respective default config generators that each command config implements.
 * @returns SailCommandConfig
 */
export function genDefaultCommandConfig() {
    return {
        lookup: genDefaultLookupConfig(),
        randomNote: genDefaultRandomNoteConfig(),
        insertNoteLink: genDefaultInsertNoteLinkConfig(),
        insertNoteIndex: genDefaultInsertNoteIndexConfig(),
        copyNoteLink: genDefaultCopyNoteLinkConfig(),
        templateHierarchy: "template",
    };
}
//# sourceMappingURL=commands.js.map