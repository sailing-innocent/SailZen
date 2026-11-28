import { SailError, DLink, NoteProps, RespV3 } from "@saili/common-all";
export type NoteMetadataValidationProps = {
    /**
     * If required, will throw error if field is missing
     */
    required?: boolean;
    /**
     * If enabled, will throw error if field is null
     */
    strictNullChecks?: boolean;
    /**
     * If enabled, will skip if field is empty
     */
    skipOnEmpty?: boolean;
};
export type NotemetadataExtractScalarProps = {
    key: string;
} & ExtractPropsCommon;
type ExtractPropsCommon = {
    note: NoteProps;
} & NoteMetadataValidationProps;
type ExtractPropWithFilter = {
    filters: string[];
} & ExtractPropsCommon;
declare enum NullOrUndefined {
    "UNDEFINED" = 0,
    "NULL" = 1,
    "NO_UNDEFINED_OR_NULL" = 2
}
export declare class NoteMetadataUtils {
    /**
     * Return list of strings from links
     * @param links
     */
    static cleanTags(links: DLink[]): string[];
    static checkIfAllowNullOrUndefined(val: any, { required, strictNullChecks }: NoteMetadataValidationProps): NullOrUndefined;
    static checkAndReturnUndefinedOrError(val: any, props: NoteMetadataValidationProps): {
        data: undefined;
        error?: undefined;
    } | {
        error: SailError<import("@saili/common-all").StatusCodes | undefined>;
        data?: undefined;
    };
    static checkIfSkipOnEmpty(key: string, val: any, props: NoteMetadataValidationProps): {
        error: SailError<import("@saili/common-all").StatusCodes | undefined>;
        data?: undefined;
    } | {
        data: any;
        error?: undefined;
    };
    /**
     * Extract string metadata from note
     * @returns
     */
    static extractString({ note, key, ...props }: NotemetadataExtractScalarProps): RespV3<string | undefined>;
    static extractNumber({ note, key, ...props }: NotemetadataExtractScalarProps): RespV3<number | undefined>;
    static extractBoolean({ note, key, ...props }: NotemetadataExtractScalarProps): RespV3<boolean | undefined>;
    static extractDate({ note, key, ...props }: NotemetadataExtractScalarProps): RespV3<string | undefined>;
    /**
     * If field is not found, return empty array
     */
    static extractArray<T>({ note, key, }: {
        key: string;
    } & ExtractPropsCommon): T[] | undefined;
    /**
     * Get all links from a note
     */
    static extractLinks({ note, filters }: ExtractPropWithFilter): DLink[];
    /**
     * Get hashtags from note
     */
    static extractTags({ note, filters }: ExtractPropWithFilter): DLink[];
    static extractSingleTag({ note, filters, }: ExtractPropWithFilter): RespV3<DLink | undefined>;
}
export {};
