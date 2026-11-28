export type SeedConfig = {
    id: string;
    name: string;
    publisher: string;
    license: string;
    root: string;
    description: string;
    repository: SeedRepository;
    contact?: SeedContact;
    /**
     * Url for seed
     */
    site?: SeedSite;
    assets?: SeedBrowserAssets;
};
export type SeedSite = {
    url: string;
    index?: string;
};
export type SeedRepository = {
    type: "git";
    url: string;
    contact?: SeedContact;
};
export type SeedContact = {
    name: string;
    email?: string;
    url?: string;
};
export declare enum SeedCommands {
    ADD = "add",
    INIT = "init",
    INFO = "info",
    REMOVE = "remove"
}
export type SeedBrowserAssets = {
    seedIcon?: string;
    publisherLogo?: string;
};
export type SeedRegistryDict = {
    [key: string]: SeedConfig | undefined;
};
export declare const SEED_REGISTRY: SeedRegistryDict;
