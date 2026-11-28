import path from "path";
import { ConfigUtils } from ".";
export class PublishUtils {
    static getPublishFM(note) {
        if (!note.custom) {
            return {};
        }
        return note.custom;
    }
    static getSEOPropsFromConfig(config) {
        const { title, twitter, description, image } = ConfigUtils.getPublishing(config).seo;
        return { title, twitter, description, image };
    }
    static getSEOPropsFromNote(note) {
        const { title, created, updated, image, desc } = note;
        const { excerpt, canonicalUrl, noindex, canonicalBaseUrl, twitter } = note.custom ? note.custom : {};
        return {
            title,
            excerpt,
            description: excerpt || desc || undefined,
            updated,
            created,
            canonicalBaseUrl,
            canonicalUrl,
            noindex,
            image,
            twitter,
        };
    }
    /**
     * Path to the banner alert compoenent
     */
    static getCustomSiteBannerPathFromWorkspace(wsRoot) {
        return path.join(wsRoot, "publish", "components", "BannerAlert.tsx");
    }
    static getCustomSiteBannerPathToPublish(publishRoot) {
        return path.join(publishRoot, "custom", "BannerAlert.tsx");
    }
    /**
     * Site banner uses a custom react component
     */
    static hasCustomSiteBanner(config) {
        return ConfigUtils.getPublishing(config).siteBanner === "custom";
    }
}
//# sourceMappingURL=publishUtils.js.map