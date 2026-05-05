/**
 * markdownBackend.ts – Blog-ready Markdown backend for SailZen Doc Engine.
 *
 * Transformation table (applied in this order to prevent mis-processing):
 *   ::cite[k1, k2]          → [k1, k2]
 *   ::figure[cap](src){…}   → ![cap](absolute_path)\n\n*cap*
 *   ::ref[label]            → (removed)
 *   ::table[cap](lbl)\n|…|  → **cap**\n\n|…| (plain MD table)
 *   ::theorem/definition/…  → > **Theorem.** …  (blockquote)
 *   ::proof                 → > *Proof.* … ∎
 *   ::algorithm[t]          → ``` code block
 *   ::if-format[markdown]   → keep content
 *   ::if-format[latex|…]    → strip content
 *   [[wikilink]]            → note title or fname plain text
 *   ![[note.ref]]           → removed (already expanded by assembler)
 *   frontmatter             → clean: title / description / date / tags
 */

import {
  AssembledDocument,
  DocExportConfig,
  DocProfile,
  GeneratedDocument,
  NoteProps,
  NotePropsByIdDict,
  ResolvedAsset,
} from "@saili/common-all";
import path from "path";

export async function generateMarkdown(
  assembled: AssembledDocument,
  profile: DocProfile,
  exportConfig: DocExportConfig,
  notesById: NotePropsByIdDict,
  wsRoot?: string
): Promise<GeneratedDocument> {
  const assetMap = new Map<string, ResolvedAsset>();
  for (const asset of profile.resolvedAssets || []) {
    assetMap.set(asset.ref, asset);
  }

  const appendRefs =
    exportConfig.vars?.appendReferences === true &&
    profile.citations.length > 0;

  const cleanBody = assembledBodyToMarkdown(assembled.body, assetMap, notesById, wsRoot);

  const rootNote = Object.values(notesById).find(
    (n) => n.id === profile.rootNoteId
  );

  const frontmatter = buildFrontmatter(profile, rootNote);
  const refsSection =
    appendRefs ? buildReferencesSection(profile.citations, notesById) : "";

  const mainContent =
    frontmatter +
    "\n\n" +
    cleanBody.trim() +
    (refsSection ? "\n\n" + refsSection : "") +
    "\n";

  return {
    mainContent,
    ext: "md",
    extraFiles: [],
    assetFiles: [],
    templateFiles: [],
    sections: undefined,
    meta: {
      templateUsed: "markdown",
      format: "markdown",
      timestamp: Date.now(),
    },
  };
}

function buildFrontmatter(
  profile: DocProfile,
  rootNote: NoteProps | undefined
): string {
  const title =
    profile.meta?.title || rootNote?.title || profile.rootNoteFname;
  const description = profile.meta?.abstract || rootNote?.desc || "";
  const rawTags = rootNote?.tags;
  const tags: string[] = rawTags
    ? Array.isArray(rawTags)
      ? rawTags
      : [rawTags]
    : [];
  const date = new Date().toISOString().split("T")[0];

  const lines = ["---", `title: "${escapeYamlString(title)}"`];
  if (description) {
    lines.push(`description: "${escapeYamlString(description)}"`);
  }
  lines.push(`date: ${date}`);
  if (tags.length > 0) {
    lines.push(
      `tags: [${tags
        .map((t) => `"${escapeYamlString(String(t))}"`)
        .join(", ")}]`
    );
  }
  lines.push("---");
  return lines.join("\n");
}

function escapeYamlString(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function buildReferencesSection(
  citations: string[],
  notesById: NotePropsByIdDict
): string {
  if (citations.length === 0) return "";
  const lines = ["## References", ""];
  for (let i = 0; i < citations.length; i++) {
    const key = citations[i];
    let label = key;
    for (const note of Object.values(notesById)) {
      const docFm = note.custom?.doc;
      if (docFm?.bibtex?.key === key) {
        label = docFm.bibtex.fields?.title || note.title || key;
        break;
      }
    }
    lines.push(`${i + 1}. ${label}`);
  }
  return lines.join("\n");
}

/**
 * Convert assembled Markdown body to clean CommonMark.
 *
 * The protect/restore pattern (Phase 1 → Phase 2 → Phase 3) is necessary
 * to prevent regex rules from matching inside already-converted spans (e.g.
 * a code block that happens to contain "::cite[…]").  Ordering within Phase 1
 * also matters: code blocks must be protected before inline code, block math
 * before inline math.
 */
function assembledBodyToMarkdown(
  md: string,
  assetMap: Map<string, ResolvedAsset>,
  notesById: NotePropsByIdDict,
  wsRoot?: string
): string {
  let text = md;
  const slots: string[] = [];

  function protect(
    re: RegExp,
    replacer: (m: string, ...args: any[]) => string
  ): void {
    text = text.replace(re, (m, ...args) => {
      const token = `\u0000${slots.length}\u0000`;
      slots.push(replacer(m, ...args));
      return token;
    });
  }

  // Phase 1 – protect content that must not be re-processed

  protect(/```(?:\w+)?\r?\n[\s\S]*?```/g, (m) => m);           // code blocks first
  protect(/\$\$[\s\S]*?\$\$/g, (m) => m);                       // block math
  protect(/(?<!\$)\$[^$\n]+?\$(?!\$)/g, (m) => m);             // inline math
  protect(/`[^`]+`/g, (m) => m);                                 // inline code

  protect(/::cite\[([^\]]+)\]/g, (_m, keys) => {
    const cleaned = keys
      .split(/,\s*/)
      .map((k: string) => k.trim())
      .filter(Boolean)
      .join(", ");
    return `[${cleaned}]`;
  });

  protect(
    /::figure\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{[^}]*\})?/g,
    (_m, caption, src) => {
      const asset = assetMap.get(src);
      const imgPath = resolveImagePath(asset?.path || src, wsRoot);
      const alt = caption || asset?.caption || src;
      const captionLine = alt ? `\n\n*${alt}*` : "";
      return `![${alt}](${imgPath})${captionLine}`;
    }
  );

  protect(/::ref\[([^\]]+)\]/g, () => "");

  protect(
    /::table\[([^\]]*)\]\s*\([^)]+\)(?:\s*\{[^}]*\})?\s*\n((?:\|[^\n]*\|[ \t]*(?:\r?\n|$))+)/g,
    (_m, caption, tableMd) =>
      (caption ? `**${caption}**\n\n` : "") + tableMd.trimEnd()
  );

  protect(
    /::table\[([^\]]*)\]\s*\([^)]+\)(?:\s*\{[^}]*\})?/g,
    (_m, caption) => (caption ? `**${caption}**` : "")
  );

  protect(
    /::(theorem|lemma|corollary|proposition|definition|remark)\[([^\]]*)\](?:\s*\{[^}]*\})?\s*\n([\s\S]*?)\n::end/g,
    (_m, env, title, content) => {
      const envName = env.charAt(0).toUpperCase() + env.slice(1);
      const titlePart = title ? ` (${title})` : "";
      const quotedBody = content
        .trim()
        .split("\n")
        .map((l: string) => `> ${l}`)
        .join("\n");
      return `> **${envName}${titlePart}.**\n${quotedBody}`;
    }
  );

  protect(
    /::proof\s*\n([\s\S]*?)\n::end/g,
    (_m, content) => {
      const quotedBody = content
        .trim()
        .split("\n")
        .map((l: string) => `> ${l}`)
        .join("\n");
      return `> *Proof.*\n${quotedBody}\n>\n> ∎`;
    }
  );

  protect(
    /::algorithm\[([^\]]*)\](?:\s*\{[^}]*\})?\s*\n([\s\S]*?)\n::end/g,
    (_m, title, content) => {
      const header = title ? `# Algorithm: ${title}\n` : "";
      return "```\n" + header + content.trim() + "\n```";
    }
  );

  protect(/::if-format\[markdown\]\s*\n([\s\S]*?)\n::end/g, (_m, c) => c);
  protect(/::if-format\[(?!markdown)[^\]]+\]\s*\n[\s\S]*?\n::end/g, () => "");

  // Phase 2 – wikilinks (safe to process now that protected slots are tokens)

  text = text.replace(/!\[\[([^\]]+)\]\]/g, "");

  text = text.replace(/\[\[([^\]#]+)#([^\]]+)\]\]/g, (_m, _fname, anchor) =>
    anchor.replace(/-/g, " ")
  );

  text = text.replace(/\[\[([^\]]+)\]\]/g, (_m, fname) => {
    const key = fname.trim();
    const note = Object.values(notesById).find((n) => n.fname === key);
    if (note?.title) return note.title;
    const segs = key.split(".");
    return segs[segs.length - 1];
  });

  // Phase 3 – restore protected slots (loop handles nested tokens)
  let prev: string;
  do {
    prev = text;
    text = text.replace(
      /\u0000(\d+)\u0000/g,
      (_m, i) => slots[parseInt(i, 10)]
    );
  } while (prev !== text);

  return text.replace(/\n{3,}/g, "\n\n");
}

function resolveImagePath(src: string, wsRoot?: string): string {
  if (!src) return src;
  if (path.isAbsolute(src) || /^https?:\/\/|^data:/.test(src)) return src;
  if (wsRoot) return path.resolve(wsRoot, src).replace(/\\/g, "/");
  return src;
}
