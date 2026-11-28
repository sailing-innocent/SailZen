import { WorkbenchProjectItemDTO } from "../../core/server/types";
import { VaultIndex } from "../../core/vault/vaultIndex";

export interface LocalContextEnrichment {
  machineId: string;
  activeFileSemanticLink?: string;
  vaultNamespace?: string;
  vaultIndex?: VaultIndex | null;
}

/**
 * Build a fallback Markdown Context Pack locally if the server hasn't deployed
 * `GET /api/v1/workbench/context-pack/{id}` yet.
 */
export function buildFallbackContextPack(proj: WorkbenchProjectItemDTO): string {
  const { progress, workbench } = proj;
  const doneCount = progress.milestones.filter(
    (m) => m.state === "DONE" || m.state === "COMPLETED"
  ).length;
  const lines: string[] = [
    `# SailZen Project Context: ${progress.title}`,
    "",
    `- **Slug**: \`${workbench.slug}\``,
    `- **Archetype**: \`${workbench.archetype}\``,
    `- **State**: \`${progress.state}\``,
  ];
  if (progress.target_date) {
    lines.push(`- **Target Date**: ${progress.target_date} (D-${progress.days_left ?? "?"})`);
  }
  if (workbench.vault_namespace) {
    lines.push(`- **Vault Namespace**: \`${workbench.vault_namespace}.*\``);
  }
  lines.push(
    `- **Progress**: ${doneCount}/${progress.milestones.length} milestones (${Math.round(
      progress.completion_ratio * 100
    )}%), recent 14d focus: ${progress.recent_14d_hours.toFixed(1)}h`
  );
  if (progress.description) {
    lines.push("", "## Description", "", progress.description.trim());
  }
  lines.push("", "## Milestones", "");
  if (progress.milestones.length === 0) {
    lines.push("- (No milestones yet)");
  } else {
    for (const ms of progress.milestones) {
      const mark = ms.state === "DONE" || ms.state === "COMPLETED" ? "x" : " ";
      lines.push(`- [${mark}] #${ms.id} ${ms.title}`);
    }
  }
  return lines.join("\n") + "\n";
}

/**
 * Enrich a cloud Context Pack with machine-local Vault recent notes & current file link
 * for pasting or feeding directly to a local Coding/Writing Agent.
 */
export function enrichContextPackWithLocalContext(
  baseMarkdown: string,
  opts: LocalContextEnrichment
): string {
  const additions: string[] = [];

  if (opts.activeFileSemanticLink) {
    additions.push(`- **Current Focus File**: ${opts.activeFileSemanticLink}`);
  }

  if (opts.vaultIndex && opts.vaultNamespace) {
    const recentNotes = opts.vaultIndex
      .search("", 12, opts.vaultNamespace)
      .map((m) => `- [[${m.note.title}|${m.note.fname}]]`);
    if (recentNotes.length > 0) {
      additions.push(
        "",
        `### Recent Local Vault Notes (\`${opts.vaultNamespace}.*\`)`,
        "",
        ...recentNotes
      );
    }
  }

  if (additions.length === 0) {
    return baseMarkdown;
  }

  return (
    baseMarkdown.trimEnd() +
    `\n\n## Local Workbench Context (${opts.machineId})\n\n` +
    additions.join("\n") +
    "\n"
  );
}
