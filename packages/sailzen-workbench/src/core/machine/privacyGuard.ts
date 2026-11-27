import { isPathInside, MachineRegistry, VaultRole } from "./machineConfig";

export type PrivacyZone = "PRIVATE_VAULT" | "WORK_VAULT" | "BOUND_REPO" | "UNKNOWN";

export class PrivacyViolationError extends Error {
  constructor(
    public readonly action: string,
    public readonly zone: PrivacyZone,
    public readonly fsPath?: string
  ) {
    super(
      `[PrivacyGuard] Blocked outbound cloud action "${action}" in zone=${zone}` +
        (fsPath ? ` (${fsPath})` : "")
    );
    this.name = "PrivacyViolationError";
  }
}

/**
 * Hard privacy firewall separating Work Vault (strictly offline) from Private Vault / Personal Cloud.
 * Any outbound write/sync/AI call containing local note content MUST pass through this guard.
 */
export class PrivacyGuard {
  constructor(private readonly registry: MachineRegistry) {}

  classifyPath(fsPath?: string): PrivacyZone {
    if (!fsPath) {
      return this.registry.getActiveVaultRole() === "work"
        ? "WORK_VAULT"
        : "PRIVATE_VAULT";
    }
    const work = this.registry.getVaultSlot("work");
    if (work?.path && isPathInside(fsPath, work.path)) {
      return "WORK_VAULT";
    }
    const priv = this.registry.getVaultSlot("private");
    if (priv?.path && isPathInside(fsPath, priv.path)) {
      return "PRIVATE_VAULT";
    }
    if (this.registry.findProjectSlugForFolder(fsPath)) {
      return "BOUND_REPO";
    }
    return "UNKNOWN";
  }

  /** Whether active vault is currently in offline Work mode. */
  isWorkOfflineActive(): boolean {
    const activeRole: VaultRole = this.registry.getActiveVaultRole();
    if (activeRole === "work") return true;
    const slot = this.registry.getVaultSlot(activeRole);
    return slot ? !slot.cloudSync : false;
  }

  /**
   * Check whether an outbound cloud request carrying content from `fsPath` (or active vault)
   * is permitted to contact personal `sail_server`.
   */
  isCloudUploadAllowed(fsPath?: string): boolean {
    if (fsPath) {
      const zone = this.classifyPath(fsPath);
      if (zone === "WORK_VAULT") return false;
      if (zone === "PRIVATE_VAULT") {
        const priv = this.registry.getVaultSlot("private");
        return priv ? priv.cloudSync : true;
      }
      // For bound repo or unknown, still block if active vault is work
      return !this.isWorkOfflineActive();
    }
    return !this.isWorkOfflineActive();
  }

  /** Throw PrivacyViolationError if uploading/sending data is forbidden. */
  assertCloudUploadAllowed(action: string, fsPath?: string): void {
    if (!this.isCloudUploadAllowed(fsPath)) {
      throw new PrivacyViolationError(action, this.classifyPath(fsPath), fsPath);
    }
  }
}
