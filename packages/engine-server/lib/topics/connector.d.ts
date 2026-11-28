import { SailConfig, DEngineClient, DVault } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
import { FSWatcher } from "fs-extra";
import { SailEngineClient } from "../engineClient";
export type EngineConnectorTarget = "cli" | "workspace";
export type EngineConnectorCommonOpts = {
    /**
     * Should initialize engine before sync?
     */
    init?: boolean;
    /**
     * Are we connecting to an engine initialized by a workspace or the CLI?
     */
    target?: EngineConnectorTarget;
};
export type EngineConnectorInitOpts = {
    onReady?: (opts: {
        ws: EngineConnector;
    }) => Promise<void>;
    numRetries?: number;
    portOverride?: number;
    fast?: boolean;
} & EngineConnectorCommonOpts;
export declare class EngineConnector {
    /**
     * Conencts to the {@link SailEngine}
     *
     * @remarks
     * Before initiating a connection, {@link EngineConnector.init} needs to be called
     */
    wsRoot: string;
    _engine: DEngineClient | undefined;
    port: number | undefined;
    onReady?: ({ ws }: {
        ws: EngineConnector;
    }) => Promise<void>;
    serverPortWatcher?: FSWatcher;
    initialized: boolean;
    config: SailConfig;
    logger: DLogger;
    static _ENGINE_CONNECTOR: EngineConnector | undefined;
    static instance(): EngineConnector;
    static getOrCreate({ wsRoot, logger, force, }: {
        wsRoot: string;
        logger?: DLogger;
        force?: boolean;
    }): EngineConnector;
    constructor({ wsRoot, logger }: {
        wsRoot: string;
        logger?: DLogger;
    });
    get vaults(): DVault[];
    /**
     * Connect with engine
     * @param opts
     * @returns
     */
    init(opts?: EngineConnectorInitOpts): Promise<void>;
    initEngine(opts: {
        engine: SailEngineClient;
        port: number;
        init?: boolean;
    }): Promise<SailEngineClient>;
    tryToConnect({ port }: {
        port: number;
    }): Promise<false | SailEngineClient>;
    get engine(): DEngineClient;
    private _connect;
    connectAndInit(opts: {
        wsRoot: string;
        init?: boolean;
    }): Promise<unknown>;
    createServerWatcher(opts?: {
        numRetries?: number;
    } & EngineConnectorCommonOpts): Promise<void>;
    onChangePort({ port }: {
        port: number;
    }): Promise<void>;
}
