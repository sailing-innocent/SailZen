/**
 * Enum definitions of possible alias mode values
 */
export var InsertNoteLinkAliasModeEnum;
(function (InsertNoteLinkAliasModeEnum) {
    InsertNoteLinkAliasModeEnum["snippet"] = "snippet";
    InsertNoteLinkAliasModeEnum["selection"] = "selection";
    InsertNoteLinkAliasModeEnum["title"] = "title";
    InsertNoteLinkAliasModeEnum["prompt"] = "prompt";
    InsertNoteLinkAliasModeEnum["none"] = "none";
})(InsertNoteLinkAliasModeEnum || (InsertNoteLinkAliasModeEnum = {}));
/**
 * Generates default {@link InsertNoteLinkConfig}
 * @returns InsertNoteLinkConfig
 */
export function genDefaultInsertNoteLinkConfig() {
    return {
        aliasMode: InsertNoteLinkAliasModeEnum.none,
        enableMultiSelect: false,
    };
}
//# sourceMappingURL=insertNoteLink.js.map