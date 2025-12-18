/**
 * Shared constants for remark plugins
 * Extracted to avoid circular dependencies between plugins
 */

/** All sorts of punctuation marks and quotation marks from different languages.
 *
 * Be warned that this excludes period (.) as it has a special meaning in Dendron.
 * Make sure to handle it appropriately depending on the context.
 *
 * Mind that this may have non regex-safe characters, run it through _.escapeRegExp if needed.
 */
export const PUNCTUATION_MARKS =
  ",;:'\"<>()?!`~\u00AB\u2039\u00BB\u203A\u201E\u201C\u201F\u201D\u2018\u275D\u275E\u276E\u276F\u2E42\u301D\u301E\u301F\uFF02\u201A\u2019\u201B\u275B\u275C\u275F\uFF3B\uFF3D\u3010\u3011\u2026\u2025\u300C\u300D\u300E\u300F\u00B7\u061F\u060C\u0964\u0965\u203D\u2E18\u00A1\u00BF\u2048\u2049";
