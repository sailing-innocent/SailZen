import { z, schemaForType } from "../../../parse";
/**
 * Generate default {@link SEOConfig}
 * @returns SEOConfig
 */
export function genDefaultSEOConfig() {
    return {
        title: "Sail",
        description: "Personal Knowledge Space",
    };
}
/**
 * `zod` schema to be used with `parse.ts` for validation.
 */
export const seoSchema = schemaForType()(z.object({
    title: z.string().optional().default("Sail"),
    description: z.string().optional().default("Personal Knowledge Space"),
    author: z.string().optional(),
    twitter: z.string().optional(),
    image: z
        .object({
        url: z.string(),
        alt: z.string(),
    })
        .optional(),
}));
//# sourceMappingURL=seo.js.map