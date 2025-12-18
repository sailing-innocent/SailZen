import { RenderNoteOpts, RenderNoteResp } from "@saili/common-all";

/**
 * Extracted from DEngine
 */
export interface INoteRenderer {
  renderNote(opts: RenderNoteOpts): Promise<RenderNoteResp>;
}
