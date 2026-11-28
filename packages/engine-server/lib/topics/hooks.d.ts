import { SailConfig, SailError, DHookEntry, DHookType, NoteProps } from "@saili/common-all";
export type RequireHookResp = {
    note: NoteProps;
    payload?: any;
};
export declare class HookUtils {
    static addToConfig({ config, hookType, hookEntry, }: {
        config: SailConfig;
        hookType: DHookType;
        hookEntry: DHookEntry;
    }): SailConfig;
    static getHookDir(wsRoot: string): string;
    static getHookScriptPath({ wsRoot, basename, }: {
        basename: string;
        wsRoot: string;
    }): string;
    static removeFromConfig({ config, hookType, hookId, }: {
        config: SailConfig;
        hookType: DHookType;
        hookId: string;
    }): SailConfig;
    static requireHook: ({ note, fpath, wsRoot, }: {
        note: NoteProps;
        fpath: string;
        wsRoot: string;
    }) => Promise<RequireHookResp>;
    static validateHook: ({ hook, wsRoot, }: {
        hook: DHookEntry;
        wsRoot: string;
    }) => {
        error: SailError<import("@saili/common-all").StatusCodes | undefined>;
        valid: boolean;
    } | {
        error: null;
        valid: boolean;
    };
}
