import { DVault } from "./DVault";
/**
 * Properties used to find notes by. If multiple properties are provided, then returned notes
 * must satisfy all constraints.
 *
 * For example, if fname = "foo" and vault = "vaultOne", then only notes with fname "foo" in vault "vaultOne" are returned
 */
export type FindNoteOpts = {
    fname?: string;
    vault?: DVault;
    excludeStub?: boolean;
};
