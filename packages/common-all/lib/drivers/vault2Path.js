import { Utils } from "vscode-uri";
import { VaultUtils } from "../vault";
/** Returns the path to where the notes are stored inside the vault.
 *
 * For self contained vaults, this is the `notes` folder inside of the vault.
 * For other vault types, this is the root of the vault itself.
 *
 * If you always need the root of the vault, use {@link pathForVaultRoot} instead.
 */
export function vault2Path({ vault, wsRoot }) {
    return Utils.joinPath(wsRoot, VaultUtils.getRelPath(vault));
}
//# sourceMappingURL=vault2Path.js.map