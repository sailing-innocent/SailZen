import { WorkbenchBootstrapDTO } from "../../core/server/types";

export const RHYTHM_FENCE_START = "<!-- sailzen:rhythm:start -->";
export const RHYTHM_FENCE_END = "<!-- sailzen:rhythm:end -->";

function hhmm(iso: string): string {
  const m = iso.match(/T(\d{2}:\d{2})/);
  return m ? m[1] : iso.slice(11, 16);
}

/** Render a concise Markdown summary of today's Rhythm timeline & active ventures. */
export function formatRhythmSnapshotMarkdown(boot: WorkbenchBootstrapDTO): string {
  const lines: string[] = [
    RHYTHM_FENCE_START,
    `> SailZen Rhythm (${boot.date}) · 已完成 ${boot.timeline.completed_minutes}m / 计划 ${boot.timeline.planned_minutes}m`,
  ];

  if (boot.timeline.ai_rationale) {
    lines.push(`> ${boot.timeline.ai_rationale.trim()}`);
  }

  if (boot.timeline.blocks.length > 0) {
    lines.push("");
    for (const blk of boot.timeline.blocks) {
      if (blk.status === "MOVED") continue;
      const box = blk.status === "DONE" ? "x" : blk.status === "DOING" ? "/" : " ";
      const label =
        blk.affair_title ||
        (typeof blk.ref?.label === "string" ? blk.ref.label : "") ||
        blk.block_type;
      const suffix = blk.status === "SKIPPED" ? " *(skipped)*" : "";
      lines.push(`- [${box}] ${hhmm(blk.start_time)}-${hhmm(blk.end_time)} ${label}${suffix}`);
    }
  } else {
    lines.push("", "- (今日暂无时间块)");
  }

  if (boot.projects.length > 0) {
    lines.push("");
    const topProjects = boot.projects.slice(0, 4).map((p) => {
      const days = p.progress.days_left !== null ? `D-${p.progress.days_left}` : "ongoing";
      const pct = Math.round(p.progress.completion_ratio * 100);
      return `${p.progress.title} (${days}, ${pct}%)`;
    });
    lines.push(`- **Active Ventures**: ${topProjects.join(" · ")}`);
  }

  lines.push(RHYTHM_FENCE_END);
  return lines.join("\n");
}

/**
 * Safely inject or update the fenced Rhythm block in a daily journal markdown file.
 * Never overwrites or disturbs handwritten content outside the managed fence.
 */
export function injectRhythmFencedSection(
  markdown: string,
  fencedBlock: string
): string {
  const startIdx = markdown.indexOf(RHYTHM_FENCE_START);
  const endIdx = markdown.indexOf(RHYTHM_FENCE_END);

  if (startIdx !== -1 && endIdx !== -1 && endIdx >= startIdx) {
    const afterEnd = endIdx + RHYTHM_FENCE_END.length;
    return markdown.slice(0, startIdx) + fencedBlock + markdown.slice(afterEnd);
  }

  // Insert right below `## Plan` if present
  const planMatch = markdown.match(/^##\s+Plan\s*$/m);
  if (planMatch && planMatch.index !== undefined) {
    const insertPos = planMatch.index + planMatch[0].length;
    const before = markdown.slice(0, insertPos);
    const after = markdown.slice(insertPos);
    return `${before}\n\n${fencedBlock}\n${after.startsWith("\n") ? after : "\n" + after}`;
  }

  const sep = markdown.endsWith("\n") ? "\n" : "\n\n";
  return `${markdown}${sep}${fencedBlock}\n`;
}
