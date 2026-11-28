import * as crypto from "crypto";
import * as fs from "fs";
import * as path from "path";
import { parseNoteContent } from "../vault/noteModel";
import { VaultIndex } from "../vault/vaultIndex";
import { SailZenApiClient } from "./apiClient";
import {
  VaultNoteIndexItemDTO,
  WorkClipsExportDTO,
  WorkDTO,
} from "./types";

export const MANAGED_META_START = "<!-- sailzen:managed:meta:start -->";
export const MANAGED_META_END = "<!-- sailzen:managed:meta:end -->";

const SYNC_NAMESPACES = ["read", "topic", "study"] as const;

/**
 * Merge a server-generated fenced metadata block into an existing local note
 * without ever overwriting or disturbing handwritten content outside the fence.
 */
export function mergeManagedMetaFence(
  existingContent: string,
  incomingMarkdown: string
): string {
  const incomingStart = incomingMarkdown.indexOf(MANAGED_META_START);
  const incomingEnd = incomingMarkdown.indexOf(MANAGED_META_END);
  const incomingFence =
    incomingStart !== -1 && incomingEnd !== -1 && incomingEnd >= incomingStart
      ? incomingMarkdown.slice(incomingStart, incomingEnd + MANAGED_META_END.length)
      : `${MANAGED_META_START}\n${incomingMarkdown.trim()}\n${MANAGED_META_END}`;

  const curStart = existingContent.indexOf(MANAGED_META_START);
  const curEnd = existingContent.indexOf(MANAGED_META_END);

  if (curStart !== -1 && curEnd !== -1 && curEnd >= curStart) {
    return (
      existingContent.slice(0, curStart) +
      incomingFence +
      existingContent.slice(curEnd + MANAGED_META_END.length)
    );
  }

  // No existing fence: insert cleanly right after YAML frontmatter (or at top)
  const fmMatch = existingContent.match(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/);
  if (fmMatch) {
    const head = existingContent.slice(0, fmMatch[0].length);
    const rest = existingContent.slice(fmMatch[0].length).replace(/^\r?\n/, "");
    return `${head}\n${incomingFence}\n\n${rest}`;
  }

  return `${incomingFence}\n\n${existingContent}`;
}

/** Collect read.* / topic.* / study.* notes from VaultIndex for upstream Content 2.0 metadata sync. */
export async function collectVaultContentNotes(
  vaultIndex: VaultIndex,
  sourceVault = "local"
): Promise<VaultNoteIndexItemDTO[]> {
  const items: VaultNoteIndexItemDTO[] = [];
  for (const note of vaultIndex.getAllNotes()) {
    const fnLower = note.fname.toLowerCase();
    const ns = SYNC_NAMESPACES.find((prefix) => fnLower.startsWith(`${prefix}.`));
    if (!ns) continue;

    let raw = "";
    try {
      raw = await fs.promises.readFile(note.fsPath, "utf8");
    } catch {
      continue;
    }

    const parsed = parseNoteContent(note.fname, raw, note.mtimeMs);
    const contentHash = crypto.createHash("sha256").update(raw, "utf8").digest("hex");

    // Extract first non-empty, non-heading line outside managed fence as summary
    const cleanBody = parsed.body
      .replace(/<!--\s*sailzen:managed:meta:start\s*-->[\s\S]*?<!--\s*sailzen:managed:meta:end\s*-->/g, "")
      .trim();
    const summaryLine =
      cleanBody
        .split(/\r?\n/)
        .map((l) => l.trim())
        .find((l) => l.length > 0 && !l.startsWith("#") && !l.startsWith("<!--")) || "";

    let pillar: string | null = null;
    if (ns === "study") {
      const seg = fnLower.split(".")[1];
      if (seg === "tech" || seg === "history" || seg === "aesthetics") {
        pillar = seg;
      }
    }

    items.push({
      fname: note.fname,
      namespace: ns,
      title: note.title,
      summary: summaryLine.slice(0, 300),
      tags: note.tags,
      links: note.links,
      pillar,
      content_hash: contentHash,
      source_vault: sourceVault,
    });
  }
  return items;
}

export interface WorkVaultExportResult {
  workId: number;
  cardPath: string;
  clipsPath: string;
  cardAction: "created" | "updated";
}

/**
 * Export a single Content 2.0 Work's reading card (fenced merge!) and clips file into local Vault.
 */
export async function writeWorkClipsToVault(
  notesDir: string,
  exp: WorkClipsExportDTO
): Promise<WorkVaultExportResult> {
  const clipsPath = path.join(notesDir, exp.clips_filename);
  const cardPath = path.join(notesDir, exp.card_filename);

  // 1. Clips file is server-managed (dedicated read.<slug>.clips.md)
  await fs.promises.writeFile(clipsPath, exp.clips_markdown, "utf8");

  // 2. Reading card merges ONLY inside managed fence so handwritten notes stay 100% intact!
  let cardAction: "created" | "updated" = "created";
  if (fs.existsSync(cardPath)) {
    const existing = await fs.promises.readFile(cardPath, "utf8");
    const merged = mergeManagedMetaFence(existing, exp.card_markdown);
    await fs.promises.writeFile(cardPath, merged, "utf8");
    cardAction = "updated";
  } else {
    await fs.promises.writeFile(cardPath, exp.card_markdown, "utf8");
  }

  return {
    workId: exp.work_id,
    cardPath,
    clipsPath,
    cardAction,
  };
}

export interface FullVaultContentSyncReport {
  upstreamProcessed: number;
  upstreamCreated: number;
  upstreamUpdated: number;
  upstreamSkipped: number;
  downstreamWorksExported: number;
}

/**
 * Full bidirectional fenced sync (equivalent to `sailzen vault sync-content`):
 * 1. Upstream: push read.* / topic.* / study.* metadata to `vault_note_index`
 * 2. Downstream: export active reading/finished works with `vault_slug` into managed fences
 */
export async function runFullVaultContentSync(
  vaultIndex: VaultIndex,
  apiClient: SailZenApiClient,
  vaultRootPath: string,
  machineId = "local"
): Promise<FullVaultContentSyncReport> {
  // 1. Upstream metadata sync (PrivacyGuard enforced inside apiClient!)
  const items = await collectVaultContentNotes(vaultIndex, machineId);
  const upRes = await apiClient.syncVaultNoteIndex(items, machineId, vaultRootPath);

  // 2. Downstream active works with vault_slug
  const works: WorkDTO[] = await apiClient.listWorks({ limit: 100 });
  const exportTargets = works.filter(
    (w) =>
      w.vault_slug &&
      w.vault_slug.trim().length > 0 &&
      (w.reading_status === "reading" || w.reading_status === "finished")
  );

  let downstreamWorksExported = 0;
  for (const w of exportTargets) {
    try {
      const exp = await apiClient.exportWorkClips(w.id);
      await writeWorkClipsToVault(vaultIndex.notesDir, exp);
      downstreamWorksExported++;
    } catch {
      // Skip individual failed work without aborting sync
    }
  }

  return {
    upstreamProcessed: upRes.total_processed,
    upstreamCreated: upRes.created,
    upstreamUpdated: upRes.updated,
    upstreamSkipped: upRes.skipped,
    downstreamWorksExported,
  };
}
