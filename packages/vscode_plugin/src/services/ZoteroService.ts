/**
 * @file ZoteroService.ts
 * @brief Zotero / Better BibTeX integration service for SailZen
 * @description Provides JSON-RPC access to Better BibTeX for:
 *   - CAYW (cite-as-you-write) picker
 *   - Citation key completion
 *   - BibTeX entry retrieval and .bib generation
 *   - Bib note generation/update
 */

import * as vscode from "vscode";
import { Logger } from "../logger";

const BBT_RPC_URL = "http://127.0.0.1:23119/better-bibtex/json-rpc";
const BBT_CAYW_URL = "http://127.0.0.1:23119/better-bibtex/cayw";

export type ZoteroItem = {
  key: string;
  citationKey: string;
  title: string;
  authors?: string[];
  year?: number;
  itemType?: string;
  [key: string]: any;
};

export type BibTeXEntry = {
  type: string;
  key: string;
  fields: Record<string, string>;
};

// ============================================================================
// JSON-RPC helpers
// ============================================================================

async function bbtRpc(method: string, params: any[]): Promise<any> {
  const resp = await fetch(BBT_RPC_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ jsonrpc: "2.0", method, params }),
  });
  const json = await resp.json();
  if (json.error) {
    throw new Error(`BBT RPC error: ${json.error.message}`);
  }
  return json.result;
}

// ============================================================================
// CAYW Picker
// ============================================================================

export async function pickCitations(
  format: "citekeys" | "markdown" | "json" = "citekeys"
): Promise<ZoteroItem[]> {
  const url = `${BBT_CAYW_URL}?format=translate&translator=csljson`;
  const response = await fetch(url);
  const text = await response.text();
  if (!text) return [];
  const items = JSON.parse(text);
  if (!Array.isArray(items)) return [];

  if (format === "citekeys") {
    return items.map((item: any) => ({
      key: item.id,
      citationKey: item.id,
      title: item.title || "",
      authors: item.author?.map((a: any) =>
        [a.family, a.given].filter(Boolean).join(", ")
      ),
      year: item.issued?.["date-parts"]?.[0]?.[0],
      itemType: item.type,
    }));
  }
  return items;
}

// ============================================================================
// Citation key completion
// ============================================================================

export async function getCitationKeys(
  query?: string
): Promise<string[]> {
  try {
    const result = await bbtRpc("item.citationkeys", [query || ""]);
    return Array.isArray(result) ? result : [];
  } catch (err) {
    Logger.info(`ZoteroService: citation key fetch failed: ${err}`);
    return [];
  }
}

// ============================================================================
// BibTeX entry retrieval
// ============================================================================

export async function getBibTeXEntry(citeKey: string): Promise<BibTeXEntry | undefined> {
  try {
    const bibtex = await bbtRpc("item.bibliography", [
      [citeKey],
      { quickCopy: true },
    ]);
    if (!bibtex) return undefined;
    return parseBibTeXEntry(bibtex);
  } catch (err) {
    Logger.info(`ZoteroService: BibTeX fetch failed for ${citeKey}: ${err}`);
    return undefined;
  }
}

export async function getBibTeXForKeys(citeKeys: string[]): Promise<string> {
  try {
    const bibtex = await bbtRpc("item.bibliography", [
      citeKeys,
      { quickCopy: true },
    ]);
    return bibtex || "";
  } catch (err) {
    Logger.info(`ZoteroService: bibliography fetch failed: ${err}`);
    return "";
  }
}

function parseBibTeXEntry(bibtexStr: string): BibTeXEntry | undefined {
  // Simple parser for single BibTeX entry
  const match = bibtexStr.match(/@(\w+)\s*\{\s*([^,\s]+)\s*,/);
  if (!match) return undefined;
  const type = match[1];
  const key = match[2];
  const fields: Record<string, string> = {};

  const fieldRegex = /(\w+)\s*=\s*\{([^}]*)\}/g;
  let fm;
  while ((fm = fieldRegex.exec(bibtexStr)) !== null) {
    fields[fm[1]] = fm[2];
  }

  return { type, key, fields };
}

// ============================================================================
// Bib note generation
// ============================================================================

export function buildBibNoteFrontmatter(entry: BibTeXEntry): string {
  const { type, key, fields } = entry;
  const title = fields.title || key;
  return `---
title: "${escapeYaml(title)}"
doc:
  role: bib
  bibtex:
    type: ${type}
    key: ${key}
    fields:
${Object.entries(fields)
  .map(([k, v]) => `      ${k}: "${escapeYaml(v)}"`)
  .join("\n")}
---

# ${title}
`;
}

function escapeYaml(value: string): string {
  return value.replace(/"/g, '\\"');
}

// ============================================================================
// Health check
// ============================================================================

export async function isZoteroRunning(): Promise<boolean> {
  try {
    const resp = await fetch(BBT_RPC_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", method: "item.citationkeys", params: [""] }),
    });
    return resp.ok;
  } catch {
    return false;
  }
}
