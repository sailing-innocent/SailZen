import { SailWorkspace } from "./SailWorkspace";

export type SailWorkspaceEntry = Omit<SailWorkspace, "name" | "vaults">;
