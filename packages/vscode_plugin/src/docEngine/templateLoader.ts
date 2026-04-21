/**
 * @file templateLoader.ts
 * @brief External template directory discovery and loading
 * @description Scans the filesystem for user-provided templates in
 *   vault/.templates/<format>/<name>/ and vault/doc/template/,
 *   parses template.yml metadata, resolves template dependencies,
 *   and provides a lightweight {{variable}} substitution engine.
 */

import {
  DocExportFormat,
  DocSection,
  DocTemplateConfig,
  DocTemplateVariable,
} from "@saili/common-all";
import { YamlUtils } from "@saili/common-all";
import fs from "fs-extra";
import path from "path";

// ============================================================================
// Types
// ============================================================================

export type ExternalTemplate = DocTemplateConfig & {
  /** Absolute path to the template directory */
  templateDir: string;
  /** Optional path to a main.tex skeleton file */
  mainTemplatePath?: string;
  /** Files listed in `requires` that exist in the template dir */
  resolvedRequires: Array<{ fileName: string; srcPath: string }>;
};

// ============================================================================
// Template directory resolution
// ============================================================================

/**
 * Resolve the directory for an external template.
 *
 * Lookup order (per design doc §6.1):
 *   1. vault/.templates/<format>/<templateId>/
 *   2. vault/doc/template/<templateId>/
 *
 * Returns the first directory that exists, or undefined.
 */
export async function resolveTemplateDir(
  templateId: string,
  format: DocExportFormat,
  wsRoot: string
): Promise<string | undefined> {
  const candidates = [
    path.join(wsRoot, ".templates", format, templateId),
    path.join(wsRoot, "doc", "template", templateId),
  ];

  for (const candidate of candidates) {
    if (await fs.pathExists(candidate)) {
      const stat = await fs.stat(candidate);
      if (stat.isDirectory()) {
        return candidate;
      }
    }
  }
  return undefined;
}

// ============================================================================
// External template loading
// ============================================================================

/**
 * Load an external template from a directory.
 *
 * Expects:
 *   - template.yml   (metadata matching DocTemplateConfig)
 *   - main.tex       (optional skeleton with {{var}} placeholders)
 *   - dependency files referenced by `requires`
 */
export async function loadExternalTemplate(
  templateDir: string
): Promise<ExternalTemplate | undefined> {
  const ymlPath = path.join(templateDir, "template.yml");
  const jsonPath = path.join(templateDir, "template.json");

  let rawMeta: any;
  if (await fs.pathExists(ymlPath)) {
    const content = await fs.readFile(ymlPath, "utf-8");
    const result = YamlUtils.fromStr(content);
    if (result.isErr()) {
      return undefined;
    }
    rawMeta = result.value;
  } else if (await fs.pathExists(jsonPath)) {
    const content = await fs.readFile(jsonPath, "utf-8");
    try {
      rawMeta = JSON.parse(content);
    } catch {
      return undefined;
    }
  } else {
    return undefined;
  }

  if (!rawMeta || typeof rawMeta !== "object") {
    return undefined;
  }

  // Normalize metadata fields
  const id = String(rawMeta.id || "");
  const format = String(rawMeta.format || "latex") as DocExportFormat;
  const description = String(rawMeta.description || "");
  const engine = rawMeta.engine || undefined;
  const requires = Array.isArray(rawMeta.requires)
    ? rawMeta.requires.map(String)
    : undefined;
  const variables: DocTemplateVariable[] | undefined = Array.isArray(
    rawMeta.variables
  )
    ? rawMeta.variables.map((v: any) => ({
        name: String(v.name || ""),
        required: Boolean(v.required),
        type: v.type,
        default: v.default,
      }))
    : undefined;
  const sectioning = rawMeta.sectioning
    ? {
        style: rawMeta.sectioning.style,
        maxDepth: rawMeta.sectioning.maxDepth,
      }
    : undefined;

  // Resolve required files that exist in the template directory
  const resolvedRequires: Array<{ fileName: string; srcPath: string }> = [];
  for (const req of requires || []) {
    const reqPath = path.join(templateDir, req);
    if (await fs.pathExists(reqPath)) {
      resolvedRequires.push({ fileName: req, srcPath: reqPath });
    }
  }

  // Check for optional main.tex / main.typ skeleton
  const mainTexPath = path.join(templateDir, "main.tex");
  const mainTypPath = path.join(templateDir, "main.typ");
  let mainTemplatePath: string | undefined;
  if (await fs.pathExists(mainTexPath)) {
    mainTemplatePath = mainTexPath;
  } else if (await fs.pathExists(mainTypPath)) {
    mainTemplatePath = mainTypPath;
  }

  return {
    id,
    format,
    description,
    engine,
    requires,
    variables,
    sectioning,
    templateDir,
    mainTemplatePath,
    resolvedRequires,
  };
}

// ============================================================================
// List external templates
// ============================================================================

/**
 * Scan for all external templates of a given format.
 *
 * Searches both lookup directories and returns a flat list.
 */
export async function listExternalTemplates(
  format: DocExportFormat,
  wsRoot: string
): Promise<DocTemplateConfig[]> {
  const results: DocTemplateConfig[] = [];
  const seen = new Set<string>();

  const searchDirs = [
    path.join(wsRoot, ".templates", format),
    path.join(wsRoot, "doc", "template"),
  ];

  for (const searchDir of searchDirs) {
    if (!(await fs.pathExists(searchDir))) {
      continue;
    }
    const entries = await fs.readdir(searchDir);
    for (const entry of entries) {
      const entryPath = path.join(searchDir, entry);
      const stat = await fs.stat(entryPath);
      if (!stat.isDirectory()) {
        continue;
      }
      const ext = await loadExternalTemplate(entryPath);
      if (ext && ext.format === format && !seen.has(ext.id)) {
        seen.add(ext.id);
        // Return only the DocTemplateConfig subset (no paths)
        const { templateDir, mainTemplatePath, resolvedRequires, ...config } =
          ext;
        results.push(config);
      }
    }
  }

  return results;
}

// ============================================================================
// Lightweight substitution engine
// ============================================================================

/**
 * Render an external template skeleton with simple {{variable}} substitution.
 *
 * Supported syntax:
 *   - {{varName}}          → string value
 *   - {{#if varName}}...{{/if}}  → conditional block
 *   - {{#each varName}}...{{/each}} → array iteration (joins with "\n")
 *
 * Arrays are auto-joined with "\n". Objects are stringified.
 */
export function renderSkeleton(
  skeleton: string,
  vars: Record<string, any>
): string {
  let result = skeleton;

  // Iteratively resolve innermost blocks first to support nesting
  while (true) {
    const ifMatch = result.match(/\{\{#if\s+(\w+)\}\}([\s\S]*?)\{\{\/if\}\}/);
    const eachMatch = result.match(
      /\{\{#each\s+(\w+)\}\}([\s\S]*?)\{\{\/each\}\}/
    );

    if (!ifMatch && !eachMatch) break;

    let earliest:
      | { type: "if"; index: number; match: RegExpMatchArray }
      | { type: "each"; index: number; match: RegExpMatchArray }
      | null = null;

    if (ifMatch) {
      earliest = { type: "if", index: ifMatch.index!, match: ifMatch };
    }
    if (eachMatch) {
      if (!earliest || eachMatch.index! < earliest.index) {
        earliest = { type: "each", index: eachMatch.index!, match: eachMatch };
      }
    }

    const m = earliest!.match;
    const start = m.index!;
    const end = start + m[0].length;

    if (earliest!.type === "if") {
      const name = m[1];
      const block = m[2];
      const val = vars[name];
      const truthy =
        val !== undefined && val !== null && val !== "" && val !== false;
      if (Array.isArray(val) && val.length === 0) {
        result = result.substring(0, start) + result.substring(end);
      } else {
        const replacement = truthy ? renderSkeleton(block, vars) : "";
        result = result.substring(0, start) + replacement + result.substring(end);
      }
    } else {
      const name = m[1];
      const block = m[2];
      const arr = vars[name];
      if (!Array.isArray(arr)) {
        result = result.substring(0, start) + result.substring(end);
      } else {
        const replacement = arr
          .map((item: any) => {
            const itemVars =
              typeof item === "object" && item !== null
                ? { ...vars, ...item }
                : { ...vars, ".": item };
            return renderSkeleton(block, itemVars);
          })
          .join("\n");
        result = result.substring(0, start) + replacement + result.substring(end);
      }
    }
  }

  // {{varName}} plain substitution
  result = result.replace(/\{\{\s*(\w+)\s*\}\}/g, (_match, name) => {
    const val = vars[name];
    if (val === undefined || val === null) {
      return "";
    }
    if (Array.isArray(val)) {
      return val.join("\n");
    }
    return String(val);
  });

  return result;
}

/**
 * Render an external template's main.tex skeleton (if present).
 *
 * Pre-formats common LaTeX constructs (authors, keywords) before substitution.
 */
export async function renderExternalTemplate(
  external: ExternalTemplate,
  vars: Record<string, any>,
  body: string,
  options?: { splitSections?: boolean; sections?: DocSection[] }
): Promise<{ mainContent: string }> {
  if (!external.mainTemplatePath) {
    throw new Error(
      `External template "${external.id}" has no skeleton`
    );
  }

  const skeleton = await fs.readFile(external.mainTemplatePath, "utf-8");

  // Pre-format helpers for common LaTeX constructs (only for LaTeX templates)
  const enrichedVars: Record<string, any> = { ...vars };
  const isLatex = external.format === "latex";

  if (isLatex) {
    // Provide escaped author fields for per-field template iteration
    if (Array.isArray(vars.authors)) {
      enrichedVars.authors = vars.authors.map((a: any) => ({
        ...a,
        name: escapeLatexSimple(a.name || ""),
        affiliation: escapeLatexSimple(a.affiliation || ""),
        country: escapeLatexSimple(a.country || "USA"),
        email: escapeLatexSimple(a.email || ""),
      }));
    }

    if (!enrichedVars.keywords_latex && Array.isArray(vars.keywords)) {
      enrichedVars.keywords_latex = vars.keywords
        .map(escapeLatexSimple)
        .join("; ");
    }

    if (vars.conference && !enrichedVars.conference_latex) {
      const c = vars.conference;
      if (typeof c === "string") {
        enrichedVars.conference_latex = `\\acmConference{${escapeLatexSimple(c)}}{}{}`;
      } else if (typeof c === "object" && c !== null) {
        const short = c.short ? `[${escapeLatexSimple(c.short)}]` : "";
        const name = escapeLatexSimple(c.name || "");
        const date = escapeLatexSimple(c.date || "");
        const venue = escapeLatexSimple(c.venue || "");
        enrichedVars.conference_latex = `\\acmConference${short}{${name}}{${date}}{${venue}}`;
      }
    }

    if (vars.year && !enrichedVars.year_latex) {
      enrichedVars.year_latex = `\\acmYear{${escapeLatexSimple(String(vars.year))}}`;
    }

    if (vars.doi && !enrichedVars.doi_latex) {
      enrichedVars.doi_latex = `\\acmDOI{${escapeLatexSimple(String(vars.doi))}}`;
    }
  }

  // Inject body
  enrichedVars.body = body;

  // Inject sections if split mode
  if (options?.splitSections && options.sections) {
    if (isLatex) {
      enrichedVars.sections = options.sections
        .map(
          (s) =>
            `\\${headingLevelToLatex(s.level)}{${escapeLatexSimple(s.title)}}\n${s.content}`
        )
        .join("\n\n");
    } else {
      // Typst uses = heading syntax
      enrichedVars.sections = options.sections
        .map(
          (s) =>
            `${"=".repeat(s.level)} ${s.title}\n${s.content}`
        )
        .join("\n\n");
    }
  }

  const mainContent = renderSkeleton(skeleton, enrichedVars);
  return { mainContent };
}

// ============================================================================
// Helpers
// ============================================================================

function escapeLatexSimple(text: string): string {
  return (
    text
      .replace(/\\/g, "\\textbackslash{}")
      .replace(/\{/g, "\\{")
      .replace(/\}/g, "\\}")
      .replace(/\$/g, "\\$")
      .replace(/&/g, "\\&")
      .replace(/#/g, "\\#")
      .replace(/\^/g, "\\^{}")
      .replace(/_/g, "\\_")
      .replace(/%/g, "\\%")
      .replace(/~/g, "\\textasciitilde{}")
  );
}

function headingLevelToLatex(level: number): string {
  switch (level) {
    case 1:
      return "section";
    case 2:
      return "subsection";
    case 3:
      return "subsubsection";
    default:
      return "paragraph";
  }
}
