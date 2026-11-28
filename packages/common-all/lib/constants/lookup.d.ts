import { AllModifierType } from "../types/lookup";
export declare const MODIFIER_DESCRIPTIONS: {
    [key in Exclude<AllModifierType, "none"> as string]: string;
};
export declare enum InvalidFilenameReason {
    EMPTY_HIERARCHY = "Hierarchies cannot be empty strings",
    LEADING_OR_TRAILING_WHITESPACE = "Hierarchies cannot contain leading or trailing whitespaces",
    ILLEGAL_CHARACTER = "Hierarchy strings cannot contain parentheses, commas, or single quotes"
}
