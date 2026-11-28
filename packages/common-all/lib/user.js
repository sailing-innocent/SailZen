import { SailUserSpecial } from "./types";
export class DUser {
    username;
    constructor(username) {
        this.username = username;
    }
    static createAnonymous() {
        return new DUser(SailUserSpecial.anonymous);
    }
    canPushVault(vault) {
        if (vault.noAutoPush) {
            return false;
        }
        if (!vault.userPermission) {
            return true;
        }
        if (vault.userPermission.write[0] === SailUserSpecial.everyone ||
            vault.userPermission.write.includes(this.username)) {
            return true;
        }
        return false;
    }
}
//# sourceMappingURL=user.js.map