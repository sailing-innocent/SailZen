import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { MachineRegistry } from "../src/core/machine/machineConfig";
import { PrivacyGuard, PrivacyViolationError } from "../src/core/machine/privacyGuard";

describe("MachineRegistry & PrivacyGuard", () => {
  let tmpRoot: string;
  let configPath: string;
  let privateDir: string;
  let workDir: string;
  let repoDir: string;

  beforeEach(() => {
    tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), "sz-machine-"));
    configPath = path.join(tmpRoot, "machine.json");
    privateDir = path.join(tmpRoot, "private-vault");
    workDir = path.join(tmpRoot, "work-vault");
    repoDir = path.join(tmpRoot, "hat-factory-repo");
    fs.mkdirSync(privateDir, { recursive: true });
    fs.mkdirSync(workDir, { recursive: true });
    fs.mkdirSync(repoDir, { recursive: true });
  });

  afterEach(() => {
    fs.rmSync(tmpRoot, { recursive: true, force: true });
  });

  it("coerces work vault cloudSync to false even if manually edited to true", () => {
    fs.writeFileSync(
      configPath,
      JSON.stringify({
        version: 1,
        machineId: "test-pc",
        role: "work",
        activeVault: "private",
        vaults: {
          private: { path: privateDir, notesDir: "notes", cloudSync: true },
          work: { path: workDir, notesDir: "notes", cloudSync: true },
        },
        projectPaths: {},
      }),
      "utf8"
    );

    const reg = new MachineRegistry(configPath);
    const loaded = reg.load();
    expect(loaded.vaults.work?.cloudSync).toBe(false);
    expect(loaded.vaults.private?.cloudSync).toBe(true);
  });

  it("blocks every outbound cloud upload from Work Vault paths or when Work Vault is active", async () => {
    const reg = new MachineRegistry(configPath);
    await reg.setVaultPath("private", privateDir);
    await reg.setVaultPath("work", workDir);
    await reg.setActiveVaultRole("private");

    const guard = new PrivacyGuard(reg);

    // Private file is allowed
    const privNote = path.join(privateDir, "notes", "journal.daily.2026.11.27.md");
    expect(guard.classifyPath(privNote)).toBe("PRIVATE_VAULT");
    expect(guard.isCloudUploadAllowed(privNote)).toBe(true);

    // Work file is ALWAYS blocked even when private vault is active!
    const workNote = path.join(workDir, "notes", "secret.company.md");
    expect(guard.classifyPath(workNote)).toBe("WORK_VAULT");
    expect(guard.isCloudUploadAllowed(workNote)).toBe(false);
    expect(() => guard.assertCloudUploadAllowed("pushTask", workNote)).toThrow(
      PrivacyViolationError
    );

    // When active vault switches to work, ALL outbound uploads are blocked
    await reg.setActiveVaultRole("work");
    expect(guard.isWorkOfflineActive()).toBe(true);
    expect(guard.isCloudUploadAllowed()).toBe(false);
    expect(() => guard.assertCloudUploadAllowed("quickChat")).toThrow(
      PrivacyViolationError
    );
  });

  it("maps semantic project slugs to machine-local paths and supports .sailzen-project.json", async () => {
    const reg = new MachineRegistry(configPath);
    await reg.bindProjectPath("hat-factory", repoDir);
    expect(reg.resolveProjectPath("hat-factory")).toBe(repoDir);
    expect(reg.findProjectSlugForFolder(path.join(repoDir, "src"))).toBe("hat-factory");

    // Unbound repo with semantic manifest file
    const otherRepo = path.join(tmpRoot, "novel-alpha");
    fs.mkdirSync(otherRepo, { recursive: true });
    fs.writeFileSync(
      path.join(otherRepo, ".sailzen-project.json"),
      JSON.stringify({ slug: "novel-alpha", archetype: "novel" }),
      "utf8"
    );
    expect(reg.findProjectSlugForFolder(otherRepo)).toBe("novel-alpha");
  });

  it("respects serverUrl precedence: machine.json > VS Code settings fallback > localhost default", () => {
    const reg = new MachineRegistry(configPath);
    // No machine.json -> uses VS Code fallback
    const fromFallback = reg.load({ serverUrl: "https://cloud.sailzen.example" });
    expect(fromFallback.serverUrl).toBe("https://cloud.sailzen.example");

    // Explicit machine.json serverUrl overrides fallback
    fs.writeFileSync(
      configPath,
      JSON.stringify({ version: 1, machineId: "pc", role: "dev", serverUrl: "https://prod.example", vaults: {}, projectPaths: {} }),
      "utf8"
    );
    const fromFile = reg.load({ serverUrl: "https://cloud.sailzen.example" });
    expect(fromFile.serverUrl).toBe("https://prod.example");
  });
});
