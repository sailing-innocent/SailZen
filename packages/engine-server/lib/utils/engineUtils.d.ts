import { SailConfig, NoteProps, ReducedDEngine, RespV3 } from "@saili/common-all";
export declare function openPortFile({ fpath }: {
    fpath: string;
}): number;
export declare class EngineUtils {
    /**
     * Try to discover file for engine port. Will use following heuristic:
     * - look for file for workspace
     * - look for file for CLI
     * @param param0
     */
    static getPortFilePath(opts: {
        wsRoot: string;
    }): RespV3<string>;
    static getPortFilePathForTarget({ wsRoot, target, }: {
        wsRoot: string;
        target: "workspace" | "cli";
    }): string;
    static getPortFilePathForWorkspace({ wsRoot }: {
        wsRoot: string;
    }): string;
    static getPortFilePathForCLI({ wsRoot }: {
        wsRoot: string;
    }): string;
    static getEnginePort(opts: {
        wsRoot: string;
    }): RespV3<number>;
    static getEnginePortForCLI(opts: {
        wsRoot: string;
    }): number;
    static getLocalEngineUrl({ port }: {
        port: number;
    }): string;
    static writeEnginePortForCLI(opts: {
        port: number;
        wsRoot: string;
    }): void;
    /**
     * Recalculate note links and anchors.
     * Modifies note in place
     *
     * NOTE: if the `note.body.length > maxNoteLength`, throw error to client informing them to increase maxNoteLength
     */
    static refreshNoteLinksAndAnchors({ note, engine, config, fmChangeOnly, silent, }: {
        note: NoteProps;
        engine: ReducedDEngine;
        config: SailConfig;
        fmChangeOnly?: boolean;
        silent?: boolean;
    }): Promise<void>;
}
