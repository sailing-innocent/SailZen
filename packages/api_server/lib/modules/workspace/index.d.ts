import { DEngineInitResp, EngineInitStatusResp, WorkspaceInitRequest, WorkspaceRequest, WorkspaceSyncRequest } from "@saili/common-all";
export declare class WorkspaceController {
    static singleton?: WorkspaceController;
    static instance(): WorkspaceController;
    /**
     * Per-workspace init queues. Inits against the same workspace (and thus the
     * same engine instance) are serialized so that a full init never runs
     * concurrently with a minimal init or another full init.
     */
    private _initQueues;
    constructor();
    /**
     * Serialize `task` behind any previously enqueued task for `wsKey`.
     */
    private _enqueue;
    init(req: WorkspaceInitRequest): Promise<DEngineInitResp>;
    private _initImpl;
    /**
     * Current engine init status for a workspace. Used by clients during
     * fast-first startup to poll for the transition from warm to ready while
     * the full index runs in the background.
     */
    initStatus({ ws }: WorkspaceRequest): Promise<EngineInitStatusResp>;
    sync({ ws }: WorkspaceSyncRequest): Promise<DEngineInitResp>;
}
