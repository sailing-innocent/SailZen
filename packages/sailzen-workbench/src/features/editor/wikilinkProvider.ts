import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { extractWikilinks, parseNoteContent } from "../../core/vault/noteModel";
import { WorkbenchState } from "../../core/workbenchState";

const REPO_LINK_RE = /repo:\/\/([a-z0-9_-]+)\/([^\s)#]+)(?:#L(\d+))?/gi;

export class SailZenEditorProviders {
  constructor(private readonly state: WorkbenchState) {}

  register(context: vscode.ExtensionContext): void {
    const mdSelector: vscode.DocumentSelector = { language: "markdown", scheme: "file" };

    // Internal link-click handler for [[wikilinks]] (supports create-if-missing!)
    context.subscriptions.push(
      vscode.commands.registerCommand(
        "sailzen._openWikilink",
        async (args: { target: string; anchor?: string }) => {
          if (!args?.target) return;
          await this.state.openOrCreateNote(args.target, { anchor: args.anchor });
        }
      ),
      vscode.commands.registerCommand(
        "sailzen._openRepoLink",
        async (args: { slug: string; relPath: string; line?: number }) => {
          if (!args?.slug || !args?.relPath) return;
          const localRoot = this.state.registry.resolveProjectPath(args.slug);
          if (!localRoot) {
            vscode.window.showWarningMessage(
              `SailZen: Project "${args.slug}" is not bound to a local folder on this machine (~/.sailzen/machine.json).`
            );
            return;
          }
          const fullPath = path.join(localRoot, args.relPath);
          if (!fs.existsSync(fullPath)) {
            vscode.window.showWarningMessage(`SailZen: File not found: ${fullPath}`);
            return;
          }
          const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(fullPath));
          const editor = await vscode.window.showTextDocument(doc, { preview: false });
          if (args.line && args.line > 0) {
            const pos = new vscode.Position(Math.min(args.line - 1, doc.lineCount - 1), 0);
            editor.selection = new vscode.Selection(pos, pos);
            editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
          }
        }
      )
    );

    // 1. [[wikilink]] autocomplete
    context.subscriptions.push(
      vscode.languages.registerCompletionItemProvider(
        mdSelector,
        {
          provideCompletionItems: (document, position) => {
            const index = this.state.vaultIndex;
            if (!index) return [];

            const linePrefix = document.lineAt(position.line).text.slice(0, position.character);
            const openIdx = linePrefix.lastIndexOf("[[");
            if (openIdx === -1) return [];
            const afterOpen = linePrefix.slice(openIdx + 2);
            if (afterOpen.includes("]]")) return [];

            // Support [[Alias|target...]] completion after `|`
            const pipeIdx = afterOpen.indexOf("|");
            const query = pipeIdx !== -1 ? afterOpen.slice(pipeIdx + 1) : afterOpen;
            const replaceStartCol = openIdx + 2 + (pipeIdx !== -1 ? pipeIdx + 1 : 0);
            const replaceRange = new vscode.Range(
              new vscode.Position(position.line, replaceStartCol),
              position
            );

            const matches = index.search(query, 40);
            return matches.map((m, idx) => {
              const item = new vscode.CompletionItem(
                m.note.fname,
                vscode.CompletionItemKind.Reference
              );
              item.detail = m.note.title;
              item.filterText = `${m.note.fname} ${m.note.title}`;
              item.sortText = String(idx).padStart(4, "0");
              item.range = replaceRange;
              item.insertText = m.note.fname;
              return item;
            });
          },
        },
        "[",
        ".",
        "|"
      )
    );

    // 2. DocumentLinkProvider: Ctrl+Click for both existing & not-yet-created [[wikilinks]] + repo:// links
    context.subscriptions.push(
      vscode.languages.registerDocumentLinkProvider(mdSelector, {
        provideDocumentLinks: (document) => {
          const text = document.getText();
          const out: vscode.DocumentLink[] = [];

          // [[wikilinks]]
          const wikilinks = extractWikilinks(text, 0);
          for (const wl of wikilinks) {
            if (wl.isEmbed) continue;
            const range = new vscode.Range(
              document.positionAt(wl.start),
              document.positionAt(wl.end)
            );
            const existing = this.state.vaultIndex?.getNote(wl.target);
            const args = encodeURIComponent(
              JSON.stringify([{ target: wl.target, anchor: wl.anchor }])
            );
            const link = new vscode.DocumentLink(
              range,
              vscode.Uri.parse(`command:sailzen._openWikilink?${args}`)
            );
            link.tooltip = existing
              ? `Open ${existing.title} (${existing.fname})`
              : `Create & Open "${wl.target}"`;
            out.push(link);
          }

          // Cross-machine semantic repo://<slug>/<path>#L10 links
          REPO_LINK_RE.lastIndex = 0;
          let m: RegExpExecArray | null;
          while ((m = REPO_LINK_RE.exec(text)) !== null) {
            const range = new vscode.Range(
              document.positionAt(m.index),
              document.positionAt(m.index + m[0].length)
            );
            const slug = m[1];
            const relPath = m[2];
            const line = m[3] ? Number(m[3]) : undefined;
            const args = encodeURIComponent(JSON.stringify([{ slug, relPath, line }]));
            const link = new vscode.DocumentLink(
              range,
              vscode.Uri.parse(`command:sailzen._openRepoLink?${args}`)
            );
            const bound = this.state.registry.resolveProjectPath(slug);
            link.tooltip = bound
              ? `Open ${relPath}${line ? `:${line}` : ""} in ${bound}`
              : `Repo "${slug}" not bound on this machine`;
            out.push(link);
          }

          return out;
        },
      })
    );

    // 3. DefinitionProvider (F12 / Go to Definition on existing [[wikilink]])
    context.subscriptions.push(
      vscode.languages.registerDefinitionProvider(mdSelector, {
        provideDefinition: (document, position) => {
          const index = this.state.vaultIndex;
          if (!index) return undefined;
          const offset = document.offsetAt(position);
          const links = extractWikilinks(document.getText(), 0);
          const hit = links.find((l) => offset >= l.start && offset <= l.end);
          if (!hit) return undefined;
          const target = index.getNote(hit.target);
          if (!target) return undefined;
          return new vscode.Location(vscode.Uri.file(target.fsPath), new vscode.Position(0, 0));
        },
      })
    );

    // 4. Lightweight Hover preview for [[wikilinks]] (zero unified/HTML overhead!)
    context.subscriptions.push(
      vscode.languages.registerHoverProvider(mdSelector, {
        provideHover: async (document, position) => {
          const index = this.state.vaultIndex;
          if (!index) return undefined;
          const offset = document.offsetAt(position);
          const links = extractWikilinks(document.getText(), 0);
          const hit = links.find((l) => offset >= l.start && offset <= l.end);
          if (!hit) return undefined;

          const target = index.getNote(hit.target);
          const md = new vscode.MarkdownString();
          md.isTrusted = false;

          if (!target) {
            md.appendMarkdown(`**${hit.target}** *(note does not exist yet — Ctrl+Click to create)*`);
            return new vscode.Hover(md);
          }

          md.appendMarkdown(`### ${target.title}\n`);
          md.appendMarkdown(`\`${target.fname}\``);
          if (target.tags.length > 0) {
            md.appendMarkdown(` · ${target.tags.map((t) => `#${t}`).join(" ")}`);
          }
          try {
            const raw = await fs.promises.readFile(target.fsPath, "utf8");
            const parsed = parseNoteContent(target.fname, raw);
            const snippet = parsed.body
              .trim()
              .split(/\r?\n/)
              .slice(0, 10)
              .join("\n")
              .slice(0, 500);
            if (snippet) {
              md.appendMarkdown(`\n\n---\n\n${snippet}`);
            }
          } catch {
            // ignore preview read error
          }
          return new vscode.Hover(md);
        },
      })
    );
  }
}
