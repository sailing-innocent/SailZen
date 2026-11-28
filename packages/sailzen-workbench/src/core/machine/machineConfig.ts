import * as fs from "fs";
import * as os from "os";
import * as path from "path";

export type VaultRole = "private" | "work";

export interface VaultSlotConfig {
  /** Root folder of the vault, e.g. D:/vault */
  path: string;
  /** Subdirectory holding .md notes, defaults to "notes" */
  notesDir?: string;
  /** Cloud sync toggle. Work vault is ALWAYS coerced to false for safety. */
  cloudSync: boolean;
}

export interface MachineConfig {
  version: number;
  machineId: string;
  role: string;
  serverUrl?: string;
  apiToken?: string;
  activeVault?: VaultRole;
  vaults: {
    private?: VaultSlotConfig;
    work?: VaultSlotConfig;
  };
  /** Semantic project slug -> local directory path on THIS machine only */
  projectPaths: Record<string, string>;
}

export interface ProjectSemanticManifest {
  slug: string;
  archetype?: string;
  vault_namespace?: string;
}

export function getDefaultMachineConfigPath(): string {
  return path.join(os.homedir(), ".sailzen", "machine.json");
}

export function normalizeFsPath(p: string): string {
  const resolved = path.resolve(p);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

export function isPathInside(targetPath: string, parentDir: string): boolean {
  const normTarget = normalizeFsPath(targetPath);
  const normParent = normalizeFsPath(parentDir);
  if (normTarget === normParent) return true;
  const sep = path.sep;
  const prefix = normParent.endsWith(sep) ? normParent : normParent + sep;
  return normTarget.startsWith(prefix);
}

/** Resolve the directory containing .md notes for a vault root. */
export function resolveVaultNotesDir(vaultRoot: string, subDir = "notes"): string {
  const candidate = path.join(vaultRoot, subDir);
  if (fs.existsSync(candidate) && fs.statSync(candidate).isDirectory()) {
    return candidate;
  }
  return vaultRoot;
}

/** Detect if a directory looks like a SailZen / Dendron vault. */
export function looksLikeVaultDir(dirPath: string): boolean {
  try {
    if (fs.existsSync(path.join(dirPath, "sail.yml"))) return true;
    if (fs.existsSync(path.join(dirPath, "dendron.yml"))) return true;
    const notesDir = path.join(dirPath, "notes");
    if (fs.existsSync(notesDir) && fs.statSync(notesDir).isDirectory()) {
      const sample = fs.readdirSync(notesDir).slice(0, 20);
      return sample.some((n) => n.endsWith(".md") && n.includes("."));
    }
  } catch {
    // ignore
  }
  return false;
}

export function createDefaultMachineConfig(): MachineConfig {
  return {
    version: 1,
    machineId: os.hostname().toLowerCase(),
    role: "dev-and-creation",
    serverUrl: "http://localhost:1974",
    activeVault: "private",
    vaults: {},
    projectPaths: {},
  };
}

export class MachineRegistry {
  public readonly configPath: string;
  private config: MachineConfig;

  constructor(configPath = getDefaultMachineConfigPath()) {
    this.configPath = configPath;
    this.config = createDefaultMachineConfig();
  }

  get current(): MachineConfig {
    return this.config;
  }

  load(fallback?: {
    serverUrl?: string;
    apiToken?: string;
    privateVaultPath?: string;
    workVaultPath?: string;
  }): MachineConfig {
    let loaded = createDefaultMachineConfig();
    let hasFileServerUrl = false;
    try {
      if (fs.existsSync(this.configPath)) {
        const raw = fs.readFileSync(this.configPath, "utf8");
        const parsed = JSON.parse(raw) as Partial<MachineConfig>;
        hasFileServerUrl = Boolean(parsed.serverUrl && parsed.serverUrl.trim());
        loaded = {
          ...loaded,
          ...parsed,
          vaults: {
            private: parsed.vaults?.private
              ? {
                  ...parsed.vaults.private,
                  notesDir: parsed.vaults.private.notesDir || "notes",
                  cloudSync: parsed.vaults.private.cloudSync !== false,
                }
              : undefined,
            work: parsed.vaults?.work
              ? {
                  ...parsed.vaults.work,
                  notesDir: parsed.vaults.work.notesDir || "notes",
                  // Hard invariant: work vault is NEVER allowed to sync to personal cloud
                  cloudSync: false,
                }
              : undefined,
          },
          projectPaths: { ...(parsed.projectPaths || {}) },
        };
      }
    } catch {
      // Malformed config file: fall back safely
    }

    if (!hasFileServerUrl && fallback?.serverUrl && fallback.serverUrl.trim()) {
      loaded.serverUrl = fallback.serverUrl.trim();
    }
    if (!loaded.serverUrl) {
      loaded.serverUrl = "http://localhost:1974";
    }
    if (!loaded.apiToken && fallback?.apiToken) {
      loaded.apiToken = fallback.apiToken;
    }
    if (!loaded.vaults.private && fallback?.privateVaultPath) {
      loaded.vaults.private = {
        path: fallback.privateVaultPath,
        notesDir: "notes",
        cloudSync: true,
      };
    }
    if (!loaded.vaults.work && fallback?.workVaultPath) {
      loaded.vaults.work = {
        path: fallback.workVaultPath,
        notesDir: "notes",
        cloudSync: false,
      };
    }

    this.config = loaded;
    return this.config;
  }

  async save(): Promise<void> {
    // Enforce work vault privacy invariant before every write
    if (this.config.vaults.work) {
      this.config.vaults.work.cloudSync = false;
    }
    const dir = path.dirname(this.configPath);
    await fs.promises.mkdir(dir, { recursive: true });
    await fs.promises.writeFile(
      this.configPath,
      JSON.stringify(this.config, null, 2) + "\n",
      "utf8"
    );
  }

  async ensureConfigFileExists(): Promise<void> {
    if (!fs.existsSync(this.configPath)) {
      await this.save();
    }
  }

  getVaultSlot(role: VaultRole): VaultSlotConfig | undefined {
    return this.config.vaults[role];
  }

  getActiveVaultRole(): VaultRole {
    if (this.config.activeVault === "work" && this.config.vaults.work) {
      return "work";
    }
    if (this.config.vaults.private) {
      return "private";
    }
    if (this.config.vaults.work) {
      return "work";
    }
    return "private";
  }

  async setActiveVaultRole(role: VaultRole): Promise<void> {
    this.config.activeVault = role;
    await this.save();
  }

  async setVaultPath(role: VaultRole, vaultPath: string): Promise<void> {
    this.config.vaults[role] = {
      path: vaultPath,
      notesDir: "notes",
      cloudSync: role === "private",
    };
    await this.save();
  }

  /** Bind a semantic project slug to a local directory on THIS machine only. */
  async bindProjectPath(slug: string, localDir: string): Promise<void> {
    const cleanSlug = slug.trim().toLowerCase();
    this.config.projectPaths[cleanSlug] = localDir;
    await this.save();
  }

  resolveProjectPath(slug: string): string | undefined {
    const cleanSlug = slug.trim().toLowerCase();
    const p = this.config.projectPaths[cleanSlug];
    return p && fs.existsSync(p) ? p : undefined;
  }

  /** Reverse-lookup semantic project slug from a local folder path on THIS machine. */
  findProjectSlugForFolder(folderPath: string): string | undefined {
    for (const [slug, boundPath] of Object.entries(this.config.projectPaths)) {
      if (isPathInside(folderPath, boundPath)) {
        return slug;
      }
    }
    // Check optional semantic manifest `.sailzen-project.json` in folder root
    try {
      const manifestPath = path.join(folderPath, ".sailzen-project.json");
      if (fs.existsSync(manifestPath)) {
        const parsed = JSON.parse(
          fs.readFileSync(manifestPath, "utf8")
        ) as Partial<ProjectSemanticManifest>;
        if (typeof parsed.slug === "string" && parsed.slug.trim()) {
          return parsed.slug.trim().toLowerCase();
        }
      }
    } catch {
      // ignore invalid manifest
    }
    return undefined;
  }
}
