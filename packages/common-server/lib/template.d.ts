import { DEngineClient, NoteProps, RespV3 } from "@saili/common-all";
export declare class TemplateUtils {
    /** The props of a template note that will get copied over when the template is applied. */
    static TEMPLATE_COPY_PROPS: readonly (keyof NoteProps)[];
    /**
     * Apply template note to provided {@param note}.
     *
     * Changes include appending template note's body to end of provided note.
     */
    static applyTemplate(opts: {
        templateNote: NoteProps;
        targetNote: NoteProps;
        engine: DEngineClient;
    }): NoteProps;
    /**
     * Given a note that has a schema:
     *  - Find template specified by schema
     *  - If there is no template found, return false
     *  - Find note by template name and apply callback `pickNote` to list of notes
     *  - Apply template note returned by callback to note and return true if applied successfully
     * If note does not have a schema, return false
     *
     * @param note: note to apply template to. This modifies the note body
     * @param pickNote: cb to pick note from list of possible template notes (can also be empty)
     * @returns boolean of whether template has been applied or not
     */
    static findAndApplyTemplate({ note, engine, pickNote, }: {
        note: NoteProps;
        engine: DEngineClient;
        pickNote: (choices: NoteProps[]) => Promise<RespV3<NoteProps | undefined>>;
    }): Promise<RespV3<boolean>>;
    static applyHBTemplate({ templateNote, targetNote, }: {
        templateNote: NoteProps;
        targetNote: NoteProps;
        engine: DEngineClient;
    }): NoteProps;
    static genTrackPayload(templateNote: NoteProps): {
        helperStats: {
            fnameToDate: number;
            eq: number;
            getDayOfWeek: number;
            match: number;
        };
    };
}
