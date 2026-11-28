/**
 * Generates a random identifier.
 *
 * Backward compatibility notes:
 * Previously this id has been generated differently including using
 * ------------------------------
 * * uuidv4(); from "uuid/v4";
 * * { v4 } from "uuid";
 * * nanoid(); from "nanoid";  uses: [A-Za-z0-9_-]
 * ------------------------------
 * Hence even though right now we only have alphanumeric ids, previously there
 * has been ids with `-` and `_` around, that still exist in our users notes.
 *
 * @returns A url-safe, random identifier.
 */
export declare const genUUID: (size?: number) => string;
/** Generates a shorter random identifier, faster but with potential cryptographic risks.
 *
 * Uses an insecure random generator for faster generation.
 * Also shortens the length of the generated IDs to 16 characters.
 * This increases the risk of collisions.
 * Only use this if performance is important and collisions are relatively unimportant.
 *
 * @returns A url-safe, random identifier.
 */
export declare const genUUIDInsecure: (size?: number) => string;
