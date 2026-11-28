import { NoteAddBehaviorEnum } from "./types";
/**
 * Generates default {@link ScratchConfig}
 * @returns ScratchConfig
 */
export function genDefaultScratchConfig() {
    return {
        name: "scratch",
        dateFormat: "y.MM.dd.HHmmss",
        addBehavior: NoteAddBehaviorEnum.asOwnDomain,
    };
}
//# sourceMappingURL=scratch.js.map