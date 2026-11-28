export declare class NodeJSUtils {
    static getVersionFromPkg(): string | undefined;
}
export type WebViewThemeMap = {
    dark: string;
    light: string;
    custom?: string;
};
export declare class WebViewCommonUtils {
    /**
     *
     * @param param0
     * @returns
     */
    static genVSCodeHTMLIndex: ({ name, jsSrc, cssSrc, url, wsRoot, browser, acquireVsCodeApi, themeMap, initialTheme, }: {
        name: string;
        jsSrc: string;
        cssSrc: string;
        url: string;
        wsRoot: string;
        browser: boolean;
        acquireVsCodeApi: string;
        themeMap: WebViewThemeMap;
        initialTheme?: string;
    }) => string;
}
