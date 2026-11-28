import { SailConfig, RespV3, WorkspaceRequest } from "@saili/common-all";
export declare class ConfigController {
    static singleton?: ConfigController;
    static instance(): ConfigController;
    get({ ws }: WorkspaceRequest): Promise<RespV3<SailConfig>>;
}
