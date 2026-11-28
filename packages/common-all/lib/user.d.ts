import { DVault } from "./types/DVault";
export declare class DUser {
    username: string;
    constructor(username: string);
    static createAnonymous(): DUser;
    canPushVault(vault: DVault): boolean;
}
