import { AssetGetRequest, AssetGetThemeRequest, RespV2 } from "@saili/common-all";
export declare class AssetsController {
    static singleton?: AssetsController;
    static instance(): AssetsController;
    get({ fpath, ws }: AssetGetRequest): Promise<RespV2<string>>;
    getTheme({ themeTarget, themeType, }: AssetGetThemeRequest): Promise<RespV2<string>>;
}
