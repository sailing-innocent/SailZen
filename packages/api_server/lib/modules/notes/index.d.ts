import { EngineInfoResp, EngineRenameNoteRequest, NoteQueryRequest, QueryNotesResp, RenameNoteResp, RenderNoteOpts, RenderNoteResp } from "@saili/common-all";
export declare class NoteController {
    static singleton?: NoteController;
    static instance(): NoteController;
    render({ ws, ...opts }: RenderNoteOpts & {
        ws: string;
    }): Promise<RenderNoteResp>;
    query({ ws, ...opts }: NoteQueryRequest): Promise<QueryNotesResp>;
    info(): Promise<EngineInfoResp>;
    rename({ ws, ...opts }: EngineRenameNoteRequest): Promise<RenameNoteResp>;
}
