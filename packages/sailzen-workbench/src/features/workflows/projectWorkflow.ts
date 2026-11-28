import * as path from "path";

/**
 * Build a cross-machine semantic source-code link:
 *   [file.ts:L42](repo://<project_slug>/<posix_rel_path>#L42)
 * Never contains drive letters or machine-specific absolute roots.
 */
export function buildSemanticRepoLink(opts: {
  projectSlug: string;
  repoRoot: string;
  fileFsPath: string;
  line?: number;
}): { uri: string; markdown: string; relPath: string } {
  const relRaw = path.relative(opts.repoRoot, opts.fileFsPath);
  if (relRaw.startsWith("..") || path.isAbsolute(relRaw)) {
    throw new Error(`File "${opts.fileFsPath}" is outside repo root "${opts.repoRoot}"`);
  }
  const relPath = relRaw.split(path.sep).join("/");
  const lineSuffix = opts.line && opts.line > 0 ? `#L${opts.line}` : "";
  const uri = `repo://${opts.projectSlug}/${relPath}${lineSuffix}`;
  const baseName = path.basename(opts.fileFsPath);
  const display = opts.line && opts.line > 0 ? `${baseName}:L${opts.line}` : baseName;
  return {
    uri,
    markdown: `[${display}](${uri})`,
    relPath,
  };
}

/**
 * Append a timestamped work/engineering/research entry cleanly under `## Record`
 * (or at end of file if `## Record` is absent) without disturbing other sections.
 */
export function appendRecordEntry(
  markdown: string,
  entryText: string,
  now: Date = new Date()
): string {
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const line = `- ${hh}:${mm} ${entryText.trim()}`;

  const recordMatch = markdown.match(/^##\s+Record\s*$/m);
  if (recordMatch && recordMatch.index !== undefined) {
    const afterHeading = recordMatch.index + recordMatch[0].length;
    const rest = markdown.slice(afterHeading);
    // Find next `## ` heading so we append at the bottom of the Record section
    const nextSecMatch = rest.match(/\r?\n##\s+/);
    if (nextSecMatch && nextSecMatch.index !== undefined) {
      const insertAt = afterHeading + nextSecMatch.index;
      const before = markdown.slice(0, insertAt).replace(/\s+$/, "");
      const after = markdown.slice(insertAt);
      return `${before}\n${line}\n${after}`;
    }
    const trimmed = markdown.replace(/\s+$/, "");
    return `${trimmed}\n${line}\n`;
  }

  const trimmed = markdown.replace(/\s+$/, "");
  return `${trimmed}\n\n${line}\n`;
}
