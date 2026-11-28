/** Kind-of parses a URI and extracts the scheme. Not an actual parser and will accept invalid URIs. */
export declare const uriRegex: RegExp;
/** Returns true if this is a non-sail uri, false if it is sail://, undefined if it's not a URI */
export declare const containsNonSailUri: (uri: string) => boolean | undefined;
export declare function isWebUri(uri: string): boolean;
export declare function isSrcUri(uri: string): boolean;
/**
 * Given a uri, determine if it is a [command uri](https://code.visualstudio.com/api/extension-guides/command#command-uris)
 * Command uris have the following scheme
 * `command:{uri}`
 */
export declare function isVSCodeCommandUri(uri: string): boolean;
