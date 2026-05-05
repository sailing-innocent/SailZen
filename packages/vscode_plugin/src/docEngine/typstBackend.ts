/**
 * @file typstBackend.ts
 * @brief Typst code generation backend for SailZen Doc Engine
 * @description Converts assembled markdown to Typst using built-in templates.
 *   Supports ::cite, ::figure, ::table, math environments, algorithms,
 *   conditionals, markdown tables, lists, footnotes, and section splitting.
 */

import {
  AssembledDocument,
  DocExportConfig,
  DocProfile,
  DocSection,
  GeneratedDocument,
  NoteProps,
  NotePropsByIdDict,
  ResolvedAsset,
} from "@saili/common-all";
import path from "path";
import { renderTemplate, resolveTemplateVars } from "./templateEngine";

// ============================================================================
// Public API
// ============================================================================

/**
 * Generate Typst output from an assembled document and profile.
 *
 * Capabilities:
 * - Template-driven document setup
 * - ::cite → @key references with #bibliography(...)
 * - ::figure → #figure(image(...), caption: [...])
 * - ::table directives with markdown table wrapping
 * - ::theorem / ::proof / ::definition / ::lemma / ::corollary / ::proposition / ::remark
 * - ::algorithm with ::input and ::output
 * - ::if-format[typst] conditional blocks
 * - Markdown tables → #table(...)
 * - Ordered/unordered lists
 * - Footnotes → #footnote(...)
 * - Optional section splitting into separate .typ files
 */
export async function generateTypst(
  assembled: AssembledDocument,
  profile: DocProfile,
  exportConfig: DocExportConfig,
  notesById: NotePropsByIdDict,
  wsRoot?: string
): Promise<GeneratedDocument> {
  const { body } = assembled;
  const { meta } = profile;

  // Build asset map for figure resolution
  const assetMap = new Map<string, ResolvedAsset>();
  for (const asset of profile.resolvedAssets || []) {
    assetMap.set(asset.ref, asset);
  }

  // Convert markdown body to Typst
  let typstBody = markdownToTypst(body, assetMap);

  // Resolve template variables
  const templateVars = resolveTemplateVars(profile, exportConfig);

  // Optional section splitting
  const splitSections = exportConfig.vars?.splitSections === true;
  let sections: DocSection[] | undefined;
  if (splitSections) {
    sections = splitIntoSections(typstBody);
  }

  // Render main.typ via template engine
  const templateId = exportConfig.template || "research-article";
  const rendered = await renderTemplate(
    templateId,
    templateVars,
    typstBody,
    {
      splitSections,
      sections,
    },
    wsRoot,
    "typst"
  );

  // Generate bibliography (Typst natively supports BibTeX)
  const bibFile = exportConfig.vars?.bibliography || "ref";
  const bibContent = generateBibTeX(profile.citations, notesById);

  // Collect asset files to copy into the project-level shared figures/ directory.
  const assetFiles: Array<{ srcPath: string; destPath: string }> = [];
  for (const asset of profile.resolvedAssets || []) {
    if (wsRoot && asset.path) {
      const srcPath =
        asset.path.startsWith("/") || /^[A-Za-z]:/.test(asset.path)
          ? asset.path
          : path.join(wsRoot, asset.path);
      const fileName = path.basename(asset.path);
      assetFiles.push({
        srcPath,
        destPath: `figures/${fileName}`,
      });
    }
  }

  const extraFiles: Array<{ path: string; content: string }> = [
    { path: `${bibFile}.bib`, content: bibContent },
  ];

  // Template dependency files are returned separately to be placed in the
  // format-specific output directory.
  const templateFiles = rendered.templateAssets || [];

  return {
    mainContent: rendered.mainContent,
    ext: "typ",
    extraFiles,
    assetFiles,
    templateFiles,
    sections,
    meta: {
      templateUsed: templateId,
      format: "typst",
      timestamp: Date.now(),
      engine: rendered.engine,
    },
  };
}

// ============================================================================
// Markdown → Typst Converter
// ============================================================================

function markdownToTypst(
  md: string,
  assetMap: Map<string, ResolvedAsset>
): string {
  let typ = md;

  // ========================================================================
  // Phase 1: Protect special blocks so inline syntax won't accidentally
  // match inside them.
  // ========================================================================
  const protectedBlocks: string[] = [];
  function protect(
    re: RegExp,
    replacer: (m: string, ...args: any[]) => string
  ): void {
    typ = typ.replace(re, (m, ...args) => {
      const placeholder = `\u0000${protectedBlocks.length}\u0000`;
      protectedBlocks.push(replacer(m, ...args));
      return placeholder;
    });
  }

  // 1.1 Protect code blocks FIRST (before inline code)
  protect(/```(\w+)?\r?\n([\s\S]*?)```/g, (_m, lang, code) => {
    const safeLang = lang || "text";
    return `#raw(block: true, lang: "${safeLang}")[${escapeTypstRaw(code.trimEnd())}]`;
  });

  // 1.2 Protect block math $$...$$
  protect(/\$\$([\s\S]*?)\$\$/g, (_m, math) => {
    return `$ ${math.trim()} $`;
  });

  // 1.2b Protect inline math $...$ (must come after block math)
  protect(/(?<!\$)\$([^$\n]+?)\$(?!\$)/g, (_m, math) => {
    return `$${math.trim()}$`;
  });

  // 1.3 Protect ::cite directives → @key references
  protect(/::cite\[([^\]]+)\]/g, (_m, keys) => {
    const cleanKeys = keys
      .split(/,\s*/)
      .map((k: string) => k.trim())
      .filter(Boolean);
    return cleanKeys.map((k: string) => `@${k}`).join(", ");
  });

  // 1.4 Protect ::figure directives
  protect(
    /::figure\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?/g,
    (_m, caption, src, optsStr) => {
      const asset = assetMap.get(src);
      const fileName = asset?.path
        ? asset.path.replace(/\\/g, "/").split("/").pop() || src
        : src;
      const typstPath = `../figures/${fileName}`;
      const figCaption = caption || asset?.caption || "";
      let figLabel = asset?.label || `fig:${src}`;
      let width = asset?.width || "80%";
      let placement = "auto";

      // Parse simple opts: width, placement, label overrides
      if (optsStr) {
        const widthMatch = optsStr.match(/width[=:]\s*"?([^",\s}]+)"?/);
        if (widthMatch) width = widthMatch[1];
        const placementMatch = optsStr.match(/placement[=:]\s*"?([^",\s}]+)"?/);
        if (placementMatch) placement = placementMatch[1];
        const labelMatch = optsStr.match(/label[=:]\s*"?([^",\s}]+)"?/);
        if (labelMatch) figLabel = labelMatch[1];
      }

      // Convert LaTeX-style widths to Typst
      let typstWidth = width;
      if (width.includes("\\textwidth")) {
        const pct = parseFloat(width) || 100;
        typstWidth = `${pct}%`;
      } else if (width.includes("\\linewidth")) {
        const pct = parseFloat(width) || 100;
        typstWidth = `${pct}%`;
      }

      const widthArg = typstWidth ? `, width: ${typstWidth}` : "";
      const placementArg = placement && placement !== "auto" ? `, placement: ${placement}` : "";

      return `#figure(
  image("${typstPath}"${widthArg}${placementArg}),
  caption: [${escapeTypstInline(figCaption)}],
) <${figLabel}>`;
    }
  );

  // 1.4b Protect ::ref directives
  protect(/::ref\[([^\]]+)\]/g, (_m, label) => {
    return `@${label}`;
  });

  // 1.5 Protect ::table directives + following markdown table
  protect(
    /::table\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?\s*\n((?:\|[^\n]*\|[ \t]*(?:\r?\n|$))+)/g,
    (_m, caption, label, _opts, tableMd) => {
      const tableBody = markdownTableToTypst(tableMd);
      return `#figure(
${tableBody},
  caption: [${escapeTypstInline(caption)}],
) <${label}>`;
    }
  );

  // 1.6 Protect standalone ::table directives (without following table)
  protect(
    /::table\[([^\]]*)\]\s*\(([^)]+)\)(?:\s*\{([^}]*)\})?/g,
    (_m, caption, label, _opts) => {
      return `#figure(
  table(columns: (auto, auto)),
  caption: [${escapeTypstInline(caption)}],
) <${label}>`;
    }
  );

  // 1.7 Protect math environments ::theorem, ::lemma, ::corollary, ::proposition, ::definition, ::remark
  protect(
    /::(theorem|lemma|corollary|proposition|definition|remark)\[([^\]]*)\](?:\s*\{([^}]*)\})?\s*\n([\s\S]*?)\n::end/g,
    (_m, env, title, opts, content) => {
      const labelMatch = opts?.match(/label:\s*"([^"]*)"/);
      const label = labelMatch ? ` <${labelMatch[1]}>` : "";
      const envName = env.charAt(0).toUpperCase() + env.slice(1);
      const titlePart = title ? ` (${escapeTypstInline(title)})` : "";
      const inner = convertInlineMarkdownToTypst(content);
      return `#block(
  stroke: (left: 2pt + rgb(100, 149, 237)),
  inset: (left: 8pt, top: 4pt, bottom: 4pt),
)[
  *${envName}${titlePart}.* ${inner}
]${label}`;
    }
  );

  // 1.8 Protect ::proof
  protect(
    /::proof\s*\n([\s\S]*?)\n::end/g,
    (_m, content) => {
      const inner = convertInlineMarkdownToTypst(content);
      return `#block(
  inset: (left: 8pt, top: 4pt, bottom: 4pt),
)[
  *Proof.* ${inner}
  #align(right)[#square(size: 6pt, stroke: none, fill: black)]
]`;
    }
  );

  // 1.9 Protect ::algorithm with ::input / ::output
  protect(
    /::algorithm\[([^\]]*)\](?:\s*\{([^}]*)\})?\s*\n([\s\S]*?)\n::end/g,
    (_m, title, opts, content) => {
      const labelMatch = opts?.match(/label:\s*"([^"]*)"/);
      const label = labelMatch ? ` <${labelMatch[1]}>` : "";
      let inner = content;
      inner = inner.replace(/::input\[([^\]]*)\]/g, (_m2: string, inp: string) => `*Input:* ${inp}`);
      inner = inner.replace(/::output\[([^\]]*)\]/g, (_m2: string, out: string) => `*Output:* ${out}`);
      // Numbered/bullet steps
      inner = inner.replace(/^(\d+)\.\s+(.+)$/gm, (_m2: string, _num: string, step: string) => `+ ${step}`);
      inner = inner.replace(/^-\s+(.+)$/gm, (_m2: string, step: string) => `+ ${step}`);
      // Indented lines as continuation
      inner = inner.replace(/^[ \t]+(.+)$/gm, (_m2: string, line: string) => `  ${line}`);
      const algoBody = convertInlineMarkdownToTypst(inner);
      return `#figure(
  caption: [${escapeTypstInline(title)}],
)[
  #set text(size: 0.9em)
  ${algoBody}
]${label}`;
    }
  );

  // 1.10 Protect ::if-format[typst] (keep content)
  protect(
    /::if-format\[typst\]\s*\n([\s\S]*?)\n::end/g,
    (_m, content) => convertInlineMarkdownToTypst(content)
  );

  // 1.11 Protect ::if-format[other] (strip content for Typst backend)
  protect(
    /::if-format\[(?!typst)[^\]]+\]\s*\n([\s\S]*?)\n::end/g,
    () => ""
  );

  // 1.12 Protect inline code `code` (AFTER code blocks)
  protect(/`([^`]+)`/g, (_m, code) => {
    return `#raw(lang: none)[${escapeTypstRaw(code)}]`;
  });

  // ========================================================================
  // Phase 2: Convert remaining markdown syntax to Typst
  // ========================================================================

  // 2.1 Headings → Typst heading syntax (=, ==, ===, etc.)
  typ = typ.replace(/^(#{1,6})\s+(.+)$/gm, (_m, hashes, text) => {
    const level = hashes.length;
    return `${"=".repeat(level)} ${escapeTypstInline(text.trim())}`;
  });

  // 2.2 Bold **text** → *text*
  typ = typ.replace(/\*\*([^*]+)\*\*/g, (_m, text) => {
    return `*${escapeTypstInline(text)}*`;
  });

  // 2.3 Italic *text* → _text_ (but not ** which is already handled)
  typ = typ.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, (_m, text) => {
    return `_${escapeTypstInline(text)}_`;
  });

  // 2.4 Links [text](url) → #link("url")[text]
  typ = typ.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text, url) => {
    return `#link("${url}")[${escapeTypstInline(text)}]`;
  });

  // 2.5 Wikilinks [[note]] → plain text (but preserve anchors ^block-id)
  typ = typ.replace(/\[\[([^\]^]+)\^([^\]]+)\]\]/g, (_m, ref, anchor) => {
    return `${escapeTypstInline(ref)}~(@${anchor})`;
  });
  typ = typ.replace(/\[\[([^\]]+)\]\]/g, (_m, ref) => {
    return escapeTypstInline(ref);
  });

  // 2.6 Note refs ![[note]] → removed (already expanded by assembler)
  typ = typ.replace(/!?\[\[([^\]]+)\]\]/g, "");

  // 2.7 Horizontal rules
  typ = typ.replace(/^---+\s*$/gm, "#line(length: 100%)\n");

  // 2.8 Blockquotes > text → #quote(block: true)[text]
  typ = typ.replace(/^>\s+(.+)$/gm, (_m, text) => {
    return `#quote(block: true)[${escapeTypstInline(text)}]`;
  });

  // 2.9 Markdown tables (not already wrapped by ::table)
  typ = convertMarkdownTables(typ);

  // 2.10 Footnotes
  typ = convertFootnotes(typ);

  // 2.11 Unordered lists (Typst uses - same as markdown)
  typ = processUnorderedLists(typ);

  // 2.12 Ordered lists (convert 1. to + for Typst auto-numbering)
  typ = processOrderedLists(typ);

  // ========================================================================
  // Phase 3: Escape remaining plain text, but protect already-generated
  // Typst commands so escapeTypst won't touch them.
  // ========================================================================

  // Protect all Typst commands we just generated
  const typstCommands: string[] = [];
  typ = typ.replace(
    /#[a-zA-Z]+(?:\[[^\]]*\]|\((?:[^()]*|\([^()]*\))*\)|"[^"]*")?/g,
    (m) => {
      const placeholder = `\u0001${typstCommands.length}\u0001`;
      typstCommands.push(m);
      return placeholder;
    }
  );

  // Also protect heading lines
  typ = typ.replace(/^={1,6}\s+.+$/gm, (m) => {
    const placeholder = `\u0001${typstCommands.length}\u0001`;
    typstCommands.push(m);
    return placeholder;
  });

  // Also protect list items
  typ = typ.replace(/^[\-+\d]\.\s+.+$/gm, (m) => {
    const placeholder = `\u0001${typstCommands.length}\u0001`;
    typstCommands.push(m);
    return placeholder;
  });

  // Now escape remaining plain text for Typst
  typ = escapeTypst(typ);

  // Restore Typst commands
  typ = typ.replace(/\u0001(\d+)\u0001/g, (_m, idx) => typstCommands[parseInt(idx, 10)]);

  // Restore protected blocks (loop to handle nested placeholders)
  let prevTyp: string;
  do {
    prevTyp = typ;
    typ = typ.replace(/\u0000(\d+)\u0000/g, (_m, idx) => protectedBlocks[parseInt(idx, 10)]);
  } while (prevTyp !== typ);

  // Multiple consecutive newlines → single paragraph break
  typ = typ.replace(/\n{3,}/g, "\n\n");

  return typ;
}

// ============================================================================
// Inline markdown converter (for use inside protected blocks)
// ============================================================================

function convertInlineMarkdownToTypst(md: string): string {
  let typ = md;

  // Protect inline math first so escapeTypst won't touch it
  const protectedMath: string[] = [];
  typ = typ.replace(/\$([^$\n]+?)\$/g, (m) => {
    const placeholder = `\u0002${protectedMath.length}\u0002`;
    protectedMath.push(m);
    return placeholder;
  });
  // Protect block math
  typ = typ.replace(/\$\$([\s\S]*?)\$\$/g, (_m, math) => {
    const placeholder = `\u0002${protectedMath.length}\u0002`;
    protectedMath.push(`$ ${math.trim()} $`);
    return placeholder;
  });

  // Bold
  typ = typ.replace(/\*\*([^*]+)\*\*/g, (_m, text) => `*${escapeTypstInline(text)}*`);
  // Italic
  typ = typ.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, (_m, text) => `_${escapeTypstInline(text)}_`);
  // Inline code
  typ = typ.replace(/`([^`]+)`/g, (_m, code) => `#raw(lang: none)[${escapeTypstRaw(code)}]`);
  // Links
  typ = typ.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_m, text, url) => `#link("${url}")[${escapeTypstInline(text)}]`);
  // Escape remaining plain text
  typ = escapeTypstInline(typ);

  // Restore math
  typ = typ.replace(/\u0002(\d+)\u0002/g, (_m, idx) => protectedMath[parseInt(idx, 10)]);
  return typ;
}

// ============================================================================
// Markdown table → Typst #table
// ============================================================================

function markdownTableToTypst(tableMd: string): string {
  const lines = tableMd.trim().split("\n").filter((l) => l.trim());
  if (lines.length < 2) return "";

  const headerCells = lines[0]
    .split("|")
    .map((c) => c.trim())
    .filter((c) => c !== "");
  const sepCells = lines[1]
    .split("|")
    .map((c) => c.trim())
    .filter((c) => c !== "");

  const aligns = sepCells.map((c) => {
    if (c.startsWith(":") && c.endsWith(":")) return "center";
    if (c.endsWith(":")) return "right";
    return "left";
  });

  // Build columns spec
  const colCount = headerCells.length;
  const columnsExpr = `(${Array(colCount).fill("auto").join(", ")})`;

  // Build align function if needed
  const hasAligns = aligns.some((a) => a !== "left");

  let cells: string[] = [];

  // Header row
  for (let i = 0; i < headerCells.length; i++) {
    const align = aligns[i];
    const cellContent = escapeTypstInline(headerCells[i]);
    if (hasAligns) {
      cells.push(`  #align(${align})[${cellContent}]`);
    } else {
      cells.push(`  [${cellContent}]`);
    }
  }

  // Data rows
  for (let i = 2; i < lines.length; i++) {
    const rowCells = lines[i]
      .split("|")
      .map((c) => c.trim())
      .filter((c) => c !== "");
    if (rowCells.length === 0) continue;
    for (let j = 0; j < rowCells.length; j++) {
      const align = aligns[j] || "left";
      const cellContent = escapeTypstInline(rowCells[j]);
      if (hasAligns) {
        cells.push(`  #align(${align})[${cellContent}]`);
      } else {
        cells.push(`  [${cellContent}]`);
      }
    }
  }

  return `  table(
    columns: ${columnsExpr},
${cells.join(",\n")},
  )`;
}

function convertMarkdownTables(typ: string): string {
  // Match standalone markdown tables (not already protected by ::table)
  const tableRegex = /^(\|[^\n]*\|[ \t]*\r?\n)(\|[-:\| \t]*\|[ \t]*\r?\n)((?:\|[^\n]*\|[ \t]*(?:\r?\n|$))+)/gm;
  return typ.replace(tableRegex, (_m, headerLine, sepLine, bodyLines) => {
    const tableMd = (headerLine + sepLine + bodyLines).trimEnd();
    return `\n${markdownTableToTypst(tableMd)}\n`;
  });
}

// ============================================================================
// Footnotes
// ============================================================================

function convertFootnotes(typ: string): string {
  const lines = typ.split("\n");
  const outLines: string[] = [];
  const footnotes: Record<string, string> = {};
  let i = 0;

  while (i < lines.length) {
    const defMatch = lines[i].match(/^\[(\^\d+)\]:\s+(.*)$/);
    if (defMatch) {
      let content = defMatch[2];
      i++;
      while (
        i < lines.length &&
        lines[i].trim() !== "" &&
        (lines[i].startsWith(" ") || lines[i].startsWith("\t"))
      ) {
        content += " " + lines[i].trim();
        i++;
      }
      footnotes[defMatch[1]] = content;
    } else {
      outLines.push(lines[i]);
      i++;
    }
  }

  let result = outLines.join("\n");
  result = result.replace(/\[(\^\d+)\]/g, (_m, num) => {
    const content = footnotes[num];
    return content ? `#footnote[${escapeTypstInline(content)}]` : `#footnote[${num}]`;
  });

  return result;
}

// ============================================================================
// Lists
// ============================================================================

function processUnorderedLists(typ: string): string {
  const lines = typ.split("\n");
  const out: string[] = [];
  let inList = false;
  let lastListLine = -1;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const listMatch = line.match(/^([ \t]*)-\s+(.+)$/);

    if (listMatch) {
      if (!inList) {
        out.push("");
      }
      out.push(`- ${listMatch[2]}`);
      lastListLine = out.length - 1;
      inList = true;
    } else {
      if (inList && line.trim() !== "" && line.match(/^[ \t]+/)) {
        if (lastListLine >= 0) {
          out[lastListLine] += " " + line.trim();
        }
      } else {
        if (inList && line.trim() === "") {
          // Empty line within list: keep it but don't end list yet
          out.push("");
        } else if (inList) {
          out.push("");
          inList = false;
        }
        out.push(line);
      }
    }
  }

  if (inList) {
    out.push("");
  }

  return out.join("\n");
}

function processOrderedLists(typ: string): string {
  const lines = typ.split("\n");
  const out: string[] = [];
  let inList = false;
  let lastListLine = -1;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const listMatch = line.match(/^[ \t]*\d+\.\s+(.+)$/);

    if (listMatch) {
      if (!inList) {
        out.push("");
      }
      out.push(`+ ${listMatch[1]}`);
      lastListLine = out.length - 1;
      inList = true;
    } else {
      if (inList && line.trim() !== "" && line.match(/^[ \t]+/)) {
        if (lastListLine >= 0) {
          out[lastListLine] += " " + line.trim();
        }
      } else {
        if (inList && line.trim() === "") {
          out.push("");
        } else if (inList) {
          out.push("");
          inList = false;
        }
        out.push(line);
      }
    }
  }

  if (inList) {
    out.push("");
  }

  return out.join("\n");
}

// ============================================================================
// Section splitting
// ============================================================================

function splitIntoSections(typstBody: string): DocSection[] {
  const lines = typstBody.split("\n");
  const sections: DocSection[] = [];
  let currentSection: DocSection | null = null;
  let currentContent: string[] = [];
  const preambleLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const match = line.match(/^(={1,6})\s+(.+)$/);

    if (match) {
      if (currentSection) {
        currentSection.content = currentContent.join("\n").trim();
        sections.push(currentSection);
      } else if (preambleLines.length > 0 && sections.length > 0) {
        // Attach orphaned preamble to first section
        sections[0].content =
          preambleLines.join("\n") + "\n\n" + sections[0].content;
      }

      const level = match[1].length;

      const safeName = match[2]
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "");

      currentSection = {
        title: match[2],
        level,
        content: line,
        fileName: `${String(sections.length).padStart(2, "0")}_${safeName}.typ`,
      };
      currentContent = [line];
    } else if (currentSection) {
      currentContent.push(line);
    } else {
      preambleLines.push(line);
    }
  }

  if (currentSection) {
    currentSection.content = currentContent.join("\n").trim();
    sections.push(currentSection);
  }

  // Attach leading preamble to first section if any
  if (preambleLines.length > 0 && sections.length > 0) {
    const preamble = preambleLines.join("\n").trim();
    if (preamble) {
      sections[0].content = preamble + "\n\n" + sections[0].content;
    }
  }

  return sections;
}

// ============================================================================
// BibTeX Generation (Typst natively supports .bib files)
// ============================================================================

function generateBibTeX(
  citations: string[],
  notesById: NotePropsByIdDict
): string {
  const entries: string[] = [];

  for (const key of citations) {
    let found = false;
    for (const note of Object.values(notesById)) {
      const docFm = note.custom?.doc;
      if (docFm?.bibtex?.key === key) {
        entries.push(bibEntryToString(docFm.bibtex));
        found = true;
        break;
      }
    }
    if (!found) {
      entries.push(
        `@misc{${key},\n  title = {${key}},\n  note = {Citation source not found in notes}\n}`
      );
    }
  }

  return entries.join("\n\n");
}

function bibEntryToString(entry: {
  type: string;
  key: string;
  fields: Record<string, string>;
}): string {
  const fieldLines = Object.entries(entry.fields).map(
    ([k, v]) => `  ${k} = {${v}}`
  );
  return `@${entry.type}{${entry.key},\n${fieldLines.join(",\n")}\n}`;
}

// ============================================================================
// Typst Escaping
// ============================================================================

/**
 * Escape plain text for Typst markup mode.
 * In Typst, backslash escapes the next character.
 */
function escapeTypst(text: string): string {
  return (
    text
      .replace(/\\/g, "\\\\")
      .replace(/#/g, "\\#")
      .replace(/\[/g, "\\[")
      .replace(/\]/g, "\\]")
      .replace(/\*/g, "\\*")
      .replace(/_/g, "\\_")
      .replace(/`/g, "\\`")
  );
}

/**
 * Escape text that will be placed inside a Typst content block [...].
 * Inside content blocks, ] ends the block, so we escape it.
 * [ does not need escaping inside content blocks (it starts a nested block).
 */
function escapeTypstInline(text: string): string {
  return (
    text
      .replace(/\\/g, "\\\\")
      .replace(/\]/g, "\\]")
      .replace(/\*/g, "\\*")
  );
}

/**
 * Escape text that will be placed inside a #raw()[...] block.
 * We need to escape ] to prevent it from ending the content block.
 */
function escapeTypstRaw(text: string): string {
  return text.replace(/\]/g, "\\]").replace(/\\/g, "\\\\");
}
