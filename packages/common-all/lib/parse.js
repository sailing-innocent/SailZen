import { z } from "zod";
import { fromZodError } from "zod-validation-error";
import { ok, err } from "./utils";
import { SailError } from "./error";
export { z };
/**
 * util for defining zod schemas with external/custom types.
 * Origin: https://github.com/colinhacks/zod/issues/372#issuecomment-826380330
 * @returns a function to be called with a zod schema
 */
export const schemaForType = () => (arg) => {
    return arg;
};
/**
 * Parse `zod` schema into `Result`
 * @param schema ZodType
 * @param raw unknown
 * @param msg string
 * @returns Result<T>
 */
export const parse = (schema, raw, msg) => {
    const parsed = schema.safeParse(raw);
    if (parsed.success) {
        return ok(parsed.data);
    }
    else {
        return err(new SailError({
            message: [
                fromZodError(parsed.error, { prefix: msg }).message,
                ...(schema.description ? [`Schema:${schema.description}`] : []),
            ].join("\n"),
        }));
    }
};
//# sourceMappingURL=parse.js.map