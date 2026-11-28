import { SailConfig, SailSiteFM, NoteProps, SEOProps } from "../types";
export declare class PublishUtils {
    static getPublishFM(note: NoteProps): SailSiteFM;
    static getSEOPropsFromConfig(config: SailConfig): Partial<SEOProps>;
    static getSEOPropsFromNote(note: NoteProps): SEOProps;
    /**
     * Path to the banner alert compoenent
     */
    static getCustomSiteBannerPathFromWorkspace(wsRoot: string): string;
    static getCustomSiteBannerPathToPublish(publishRoot: string): string;
    /**
     * Site banner uses a custom react component
     */
    static hasCustomSiteBanner(config: SailConfig): boolean;
}
