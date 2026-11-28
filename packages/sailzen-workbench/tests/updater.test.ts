import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { SailZenApiClient } from "../src/core/server/apiClient";
import { WorkbenchReleaseInfoDTO } from "../src/core/server/types";
import {
  checkForWorkbenchUpdate,
  compareSemver,
  computeBufferSha256,
  downloadAndVerifyVsix,
} from "../src/core/server/updater";

describe("VS Code Workbench OTA Updater", () => {
  it("compares semver strings accurately", () => {
    expect(compareSemver("0.3.1", "0.3.0")).toBeGreaterThan(0);
    expect(compareSemver("0.4.0", "0.3.9")).toBeGreaterThan(0);
    expect(compareSemver("1.0.0", "0.9.9")).toBeGreaterThan(0);
    expect(compareSemver("0.3.0", "0.3.0")).toBe(0);
    expect(compareSemver("0.2.9", "0.3.0")).toBeLessThan(0);
    expect(compareSemver("v0.3.2", "0.3.1")).toBeGreaterThan(0);
  });

  it("checks latest release and verifies SHA-256 on VSIX download", async () => {
    const payload = Buffer.from("fake-vsix-zip-content", "utf8");
    const goodSha = computeBufferSha256(payload);
    const release: WorkbenchReleaseInfoDTO = {
      version: "0.4.0",
      file_name: "sailzen-workbench-0.4.0.vsix",
      size: payload.length,
      sha256: goodSha,
      release_notes: "OTA update support",
      published_at: "2026-11-28T10:30:00+08:00",
      download_path: "/api/v1/workbench/release/download/sailzen-workbench-0.4.0.vsix",
    };

    const mockClient = {
      getLatestWorkbenchRelease: async () => release,
      downloadBinary: async () => payload,
    } as unknown as SailZenApiClient;

    const check = await checkForWorkbenchUpdate(mockClient, "0.3.0");
    expect(check.hasUpdate).toBe(true);
    expect(check.release.version).toBe("0.4.0");

    const upToDate = await checkForWorkbenchUpdate(mockClient, "0.4.0");
    expect(upToDate.hasUpdate).toBe(false);

    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "sz-ota-"));
    try {
      const savedPath = await downloadAndVerifyVsix(mockClient, release, tmpDir);
      expect(fs.existsSync(savedPath)).toBe(true);
      expect(fs.readFileSync(savedPath)).toEqual(payload);

      // Corrupted SHA-256 must be rejected
      await expect(
        downloadAndVerifyVsix(
          mockClient,
          { ...release, sha256: "0".repeat(64) },
          tmpDir
        )
      ).rejects.toThrow(/SHA-256 mismatch/i);
    } finally {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }
  });
});
