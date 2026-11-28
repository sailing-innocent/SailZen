export declare function isAlias(pageTitle: string): boolean;
export declare const ALIAS_DIVIDER = "|";
/** A regexp fragment that matches a link name (e.g. a note name) */
export declare const LINK_NAME = "[^#\\|>\\]\\[\\n]+";
export declare const LINK_NAME_NO_SPACES = "[^#\\|>\\]\\[\\n\\s]+";
/** A regexp fragment that matches an alias name */
export declare const ALIAS_NAME = "[^\\|>\\]\\[\\n]+";
/** A regexp fragment that matches the contents of a link (without the brackets) */
export declare const LINK_CONTENTS: string;
