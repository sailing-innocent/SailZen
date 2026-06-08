/**
 * @file Zotero.ts
 * @brief Zotero / Better BibTeX integration commands for SailZen
 * @author sailing-innocent
 * @date 2025-06-03
 */

import * as vscode from "vscode";
import { Logger } from "../logger";
import {
  pickCitations,
  getBibTeXEntry,
  buildBibNoteFrontmatter,
  isZoteroRunning,
} from "../services/ZoteroService";

/**
 * Show Zotero CAYW picker and insert ::cite[key] into the active editor.
 */
export async function showZoteroPicker(): Promise<void> {
  try {
    const running = await isZoteroRunning();
    if (!running) {
      vscode.window.showErrorMessage(
        "Zotero Citations: could not connect to Zotero. Are you sure it is running with Better BibTeX?"
      );
      return;
    }

    const items = await pickCitations("citekeys");
    if (!items || items.length === 0) return;

    const keys = items.map((i) => i.citationKey);
    const citeStr = `::cite[${keys.join(", ")}]`;

    const editor = vscode.window.activeTextEditor;
    if (editor) {
      await editor.edit((editBuilder) => {
        editor.selections.forEach((selection) => {
          editBuilder.replace(selection, citeStr);
        });
      });
    }
  } catch (err: any) {
    Logger.error({ ctx: "ZoteroPicker", msg: err.message });
    vscode.window.showErrorMessage(
      `Zotero Citations: ${err.message}`
    );
  }
}

/**
 * Import the selected Zotero item as a SailZen bib note.
 */
export async function importZoteroAsBibNote(): Promise<void> {
  try {
    const running = await isZoteroRunning();
    if (!running) {
      vscode.window.showErrorMessage("Zotero not running with Better BibTeX.");
      return;
    }

    const items = await pickCitations("citekeys");
    if (!items || items.length === 0) return;

    for (const item of items) {
      const entry = await getBibTeXEntry(item.citationKey);
      if (!entry) {
        vscode.window.showWarningMessage(
          `Could not fetch BibTeX for ${item.citationKey}`
        );
        continue;
      }

      const fm = buildBibNoteFrontmatter(entry);
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        const doc = editor.document;
        const endPos = new vscode.Position(doc.lineCount, 0);
        await editor.edit((eb) => {
          eb.insert(endPos, "\n\n" + fm);
        });
      } else {
        vscode.env.clipboard.writeText(fm);
        vscode.window.showInformationMessage(
          `Bib note frontmatter for ${item.citationKey} copied to clipboard.`
        );
      }
    }
  } catch (err: any) {
    Logger.error({ ctx: "ZoteroImport", msg: err.message });
    vscode.window.showErrorMessage(`Zotero import failed: ${err.message}`);
  }
}

async function openInZotero(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;

  let citeKey = "";
  if (editor.selection.isEmpty) {
    const range = editor.document.getWordRangeAtPosition(
      editor.selection.active
    );
    if (range) {
      citeKey = editor.document.getText(range);
    }
  } else {
    citeKey = editor.document.getText(
      new vscode.Range(editor.selection.start, editor.selection.end)
    );
  }

  if (!citeKey) return;
  const uri = vscode.Uri.parse(`zotero://select/items/bbt:${citeKey}`);
  await vscode.env.openExternal(uri);
}

async function openPDFZotero(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) return;

  let citeKey = "";
  if (editor.selection.isEmpty) {
    const range = editor.document.getWordRangeAtPosition(
      editor.selection.active
    );
    if (range) {
      citeKey = editor.document.getText(range);
    }
  } else {
    citeKey = editor.document.getText(
      new vscode.Range(editor.selection.start, editor.selection.end)
    );
  }

  if (!citeKey) return;

  let uri = vscode.Uri.parse(`zotero://select/items/bbt:${citeKey}`);
  try {
    const response = await fetch(
      "http://localhost:23119/better-bibtex/json-rpc",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          jsonrpc: "2.0",
          method: "item.attachments",
          params: [citeKey],
        }),
      }
    );
    const repos: any = await response.json();
    for (const elt of repos["result"] || []) {
      if (elt["path"]?.endsWith(".pdf")) {
        uri = vscode.Uri.parse(elt["open"]);
        break;
      }
    }
    await vscode.env.openExternal(uri);
  } catch (err: any) {
    Logger.error({ ctx: "ZoteroPDF", msg: err.message });
    await vscode.env.openExternal(uri);
  }
}

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("dendron.zotero.openInZotero", openInZotero)
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("dendron.zotero.openPDFZotero", openPDFZotero)
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("dendron.zotero.CitationPicker", showZoteroPicker)
  );
  context.subscriptions.push(
    vscode.commands.registerCommand(
      "dendron.zotero.importAsBibNote",
      importZoteroAsBibNote
    )
  );
}

export function deactivate(): void {
  // cleanup
}
