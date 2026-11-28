import * as crypto from "crypto";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { SailZenApiClient } from "./apiClient";
import { WorkbenchReleaseInfoDTO } from "./types";

/**
 * Compare two semver strings (`X.Y.Z`).
 * Returns >0 if a > b, 0 if equal, <0 if a < b.
 */
export function compareSemver(a: string, b: string): number {
  const parse = (v: string): [number, number, number] => {
    const clean = v.trim().replace(/^v/i, "").split("-")[0];
    const parts = clean.split(".").map((n) => Number.parseInt(n, 10) || 0);
    return [parts[0] || 0, parts[1] || 0, parts[2] || 0];
  };
  const [a1, a2, a3] = parse(a);
  const [b1, b2, b3] = parse(b);
  if (a1 !== b1) return a1 - b1;
  if (a2 !== b2) return a2 - b2;
  return a3 - b3;
}

export function computeBufferSha256(buf: Buffer): string {
  return crypto.createHash("sha256").update(buf).digest("hex");
}

export interface UpdateCheckResult {
  hasUpdate: boolean;
  currentVersion: string;
  release: WorkbenchReleaseInfoDTO;
}

/** Query cloud sail_server for latest VSIX release metadata. */
export async function checkForWorkbenchUpdate(
  apiClient: SailZenApiClient,
  currentVersion: string
): Promise<UpdateCheckResult> {
  const release = await apiClient.getLatestWorkbenchRelease();
  const hasUpdate = compareSemver(release.version, currentVersion) > 0;
  return { hasUpdate, currentVersion, release };
}

/**
 * Download the VSIX from sail_server, verify its SHA-256 checksum (if provided),
 * and write it to a temporary local path ready for `workbench.extensions.installExtension`.
 */
export async function downloadAndVerifyVsix(
  apiClient: SailZenApiClient,
  release: WorkbenchReleaseInfoDTO,
  targetDir = os.tmpdir()
): Promise<string> {
  const downloadTarget = release.download_path || "/api/v1/workbench/release/latest.vsix";
  const buf = await apiClient.downloadBinary(downloadTarget);
  if (buf.length === 0) {
    throw new Error("Downloaded VSIX is empty.");
  }

  if (release.sha256 && release.sha256.trim()) {
    const actual = computeBufferSha256(buf);
    if (actual.toLowerCase() !== release.sha256.trim().toLowerCase()) {
      throw new Error(
        `VSIX SHA-256 mismatch: expected ${release.sha256.slice(0, 12)}..., got ${actual.slice(0, 12)}...`
      );
    }
  }

  const safeName = (release.file_name || `sailzen-workbench-${release.version}.vsix`).replace(
    /[^A-Za-z0-9._-]/g,
    "_"
  );
  const outPath = path.join(targetDir, `sailzen-ota-${Date.now()}-${safeName}`);
  await fs.promises.writeFile(outPath, buf);
  return outPath;
}
