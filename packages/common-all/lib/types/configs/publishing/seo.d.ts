import { z } from "../../../parse";
/**
 * Namespace for SEO related site configurations.
 */
export type SEOConfig = {
    title?: string;
    description?: string;
    author?: string;
    twitter?: string;
    image?: SEOImage;
};
export type SEOImage = {
    url: string;
    alt: string;
};
/**
 * Generate default {@link SEOConfig}
 * @returns SEOConfig
 */
export declare function genDefaultSEOConfig(): SEOConfig;
/**
 * `zod` schema to be used with `parse.ts` for validation.
 */
export declare const seoSchema: z.ZodObject<{
    title: z.ZodDefault<z.ZodOptional<z.ZodString>>;
    description: z.ZodDefault<z.ZodOptional<z.ZodString>>;
    author: z.ZodOptional<z.ZodString>;
    twitter: z.ZodOptional<z.ZodString>;
    image: z.ZodOptional<z.ZodObject<{
        url: z.ZodString;
        alt: z.ZodString;
    }, z.core.$strip>>;
}, z.core.$strip>;
