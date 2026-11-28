import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import { SailZenVfsUri } from "../../core/server/virtualFs";
import {
  extractHeadings,
  extractHeadingSection,
  extractWikilinks,
  findHeadingLine,
  parseNoteContent,
} from "../../core/vault/noteModel";
import { WorkbenchState } from "../../core/workbenchState";

const REPO_LINK_RE = /repo:\/\/([a-z0-9_-]+)\/([^\s)#<>\[\]]+)(?:#L(\d+))?/gi;

export class SailZenEditorProviders {
  private readonly existingLinkDecoration: vscode.TextEditorDecorationType;
  private readonly missingLinkDecoration: vscode.TextEditorDecorationType;
  private readonly embedLinkDecoration: vscode.TextEditorDecorationType;
  private readonly repoLinkDecoration: vscode.TextEditorDecorationType;
  private readonly _onDidChangeCodeLenses = new vscode.EventEmitter<void>();
  private decorateTimer: NodeJS.Timeout | null = null;

  constructor(private readonly state: WorkbenchState) {
    this.existingLinkDecoration = vscode.window.createTextEditorDecorationType({
      color: new vscode.ThemeColor("textLink.foreground"),
      textDecoration: "underline",
    });
    this.missingLinkDecoration = vscode.window.createTextEditorDecorationType({
      color: new vscode.ThemeColor("editorWarning.foreground"),
      textDecoration: "underline dotted",
    });
    this.embedLinkDecoration = vscode.window.createTextEditorDecorationType({
      color: new vscode.ThemeColor("textLink.activeForeground"),
      backgroundColor: new vscode.ThemeColor("editor.wordHighlightBackground"),
      borderRadius: "3px",
    });
    this.repoLinkDecoration = vscode.window.createTextEditorDecorationType({
      color: new vscode.ThemeColor("textLink.foreground"),
      border: "1px solid",
      borderColor: new vscode.ThemeColor("textLink.foreground"),
      borderRadius: "3px",
    });
  }

  register(context: vscode.ExtensionContext): void {
    const mdSelector: vscode.DocumentSelector = { language: "markdown", scheme: "file" };

    context.subscriptions.push(
      this.existingLinkDecoration,
      this.missingLinkDecoration,
      this.embedLinkDecoration,
      this.repoLinkDecoration,
      this._onDidChangeCodeLenses,
      {
        dispose: () => {
          if (this.decorateTimer) {
            clearTimeout(this.decorateTimer);
            this.decorateTimer = null;
          }
        },
      }
    );

    // Internal link-click handlers for [[wikilinks]], [[#anchors]], and repo:// links
    context.subscriptions.push(
      vscode.commands.registerCommand(
        "sailzen._openWikilink",
        async (args: { target?: string; anchor?: string; sourceFsPath?: string }) => {
          if (!args) return;
          if (!args.target && args.anchor) {
            await this.jumpToLocalHeading(args.anchor, args.sourceFsPath);
            return;
          }
          if (!args.target) return;
          await this.state.openOrCreateNote(args.target, { anchor: args.anchor });
        }
      ),
      vscode.commands.registerCommand(
        "sailzen._openRepoLink",
        async (args: { slug: string; relPath: string; line?: number }) => {
          await this.openRepoLink(args);
        }
      )
    );

    // 1. [[wikilink]] & [[target#heading]] autocomplete
    context.subscriptions.push(
      vscode.languages.registerCompletionItemProvider(
        mdSelector,
        {
          provideCompletionItems: async (document, position) => {
            const index = this.state.vaultIndex;
            if (!index) return [];

            const lineText = document.lineAt(position.line).text;
            const linePrefix = lineText.slice(0, position.character);
            const openIdx = linePrefix.lastIndexOf("[[");
            if (openIdx === -1) return [];
            const afterOpen = linePrefix.slice(openIdx + 2);
            if (afterOpen.includes("]]")) return [];

            // Support [[Alias|target#heading]] completion
            const pipeIdx = afterOpen.indexOf("|");
            const targetSegment = pipeIdx !== -1 ? afterOpen.slice(pipeIdx + 1) : afterOpen;
            const targetSegmentStartCol = openIdx + 2 + (pipeIdx !== -1 ? pipeIdx + 1 : 0);

            // Heading completion after `#`: `[[#...` or `[[some.note#...`
            const hashIdx = targetSegment.indexOf("#");
            if (hashIdx !== -1) {
              const targetFname = targetSegment.slice(0, hashIdx).trim();
              const headingQuery = targetSegment.slice(hashIdx + 1).toLowerCase();
              const replaceRange = new vscode.Range(
                new vscode.Position(position.line, targetSegmentStartCol + hashIdx + 1),
                position
              );

              let rawText: string | undefined;
              if (!targetFname) {
                rawText = document.getText();
              } else {
                const targetNote = index.getNote(targetFname);
                if (targetNote) {
                  try {
                    rawText = await fs.promises.readFile(targetNote.fsPath, "utf8");
                  } catch {
                    rawText = undefined;
                  }
                }
              }
              if (!rawText) return [];

              const headings = extractHeadings(rawText);
              return headings
                .filter(
                  (h) =>
                    !headingQuery ||
                    h.text.toLowerCase().includes(headingQuery) ||
                    h.slug.includes(headingQuery)
                )
                .map((h, idx) => {
                  const item = new vscode.CompletionItem(
                    h.text,
                    vscode.CompletionItemKind.Struct
                  );
                  item.detail = `${"#".repeat(h.level)} ${h.slug}`;
                  item.filterText = `${h.text} ${h.slug}`;
                  item.sortText = String(idx).padStart(4, "0");
                  item.range = replaceRange;
                  item.insertText = h.slug || h.text;
                  return item;
                });
            }

            // Standard note fname completion
            const query = targetSegment;
            const replaceRange = new vscode.Range(
              new vscode.Position(position.line, targetSegmentStartCol),
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
        "|",
        "#"
      )
    );

    // 2. DocumentLinkProvider: Ctrl+Click for [[wikilinks]], ![[embeds]], [[#anchors]], & repo:// links
    context.subscriptions.push(
      vscode.languages.registerDocumentLinkProvider(mdSelector, {
        provideDocumentLinks: (document) => {
          const text = document.getText();
          const out: vscode.DocumentLink[] = [];

          const wikilinks = extractWikilinks(text, 0);
          for (const wl of wikilinks) {
            const range = new vscode.Range(
              document.positionAt(wl.start),
              document.positionAt(wl.end)
            );
            const args = encodeURIComponent(
              JSON.stringify([
                {
                  target: wl.target,
                  anchor: wl.anchor,
                  sourceFsPath: document.uri.fsPath,
                },
              ])
            );
            const link = new vscode.DocumentLink(
              range,
              vscode.Uri.parse(`command:sailzen._openWikilink?${args}`)
            );

            if (!wl.target && wl.anchor) {
              link.tooltip = `Jump to heading #${wl.anchor}`;
            } else {
              const existing = this.state.vaultIndex?.getNote(wl.target);
              const prefix = wl.isEmbed ? "Open embedded note" : "Open";
              link.tooltip = existing
                ? `${prefix} ${existing.title} (${existing.fname})${wl.anchor ? `#${wl.anchor}` : ""}`
                : `Create & Open "${wl.target}"`;
            }
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

    // 3. DefinitionProvider (F12 / Peek Definition on [[wikilink]], ![[embed]], or [[#anchor]])
    context.subscriptions.push(
      vscode.languages.registerDefinitionProvider(mdSelector, {
        provideDefinition: async (document, position) => {
          const index = this.state.vaultIndex;
          if (!index) return undefined;
          const offset = document.offsetAt(position);
          const links = extractWikilinks(document.getText(), 0);
          const hit = links.find((l) => offset >= l.start && offset <= l.end);
          if (!hit) return undefined;

          // Same-file anchor [[#heading]]
          if (!hit.target && hit.anchor) {
            const targetLine = findHeadingLine(document.getText(), hit.anchor) ?? 0;
            return new vscode.Location(document.uri, new vscode.Position(targetLine, 0));
          }

          const target = index.getNote(hit.target);
          if (!target) return undefined;

          let targetLine = 0;
          if (hit.anchor) {
            try {
              const raw = await fs.promises.readFile(target.fsPath, "utf8");
              targetLine = findHeadingLine(raw, hit.anchor) ?? 0;
            } catch {
              targetLine = 0;
            }
          }
          return new vscode.Location(
            vscode.Uri.file(target.fsPath),
            new vscode.Position(targetLine, 0)
          );
        },
      })
    );

    // 4. ReferenceProvider (Shift+F12 / Peek References -> native vault-wide Backlinks!)
    context.subscriptions.push(
      vscode.languages.registerReferenceProvider(mdSelector, {
        provideReferences: async (document, position) => {
          const index = this.state.vaultIndex;
          if (!index) return [];

          // If cursor is on a [[wikilink]], find vault references to that target;
          // if cursor is in frontmatter/top lines (0..5), return backlinks to current note;
          // otherwise yield [] so VS Code's native Markdown ReferenceProvider handles headings & standard links cleanly.
          const offset = document.offsetAt(position);
          const linksInDoc = extractWikilinks(document.getText(), 0);
          const hit = linksInDoc.find(
            (l) => l.target.length > 0 && offset >= l.start && offset <= l.end
          );

          const targetFname =
            hit?.target ||
            (position.line <= 5 ? this.state.getNoteFnameForPath(document.uri.fsPath) : undefined);
          if (!targetFname) return [];

          const targetKey = targetFname.toLowerCase();
          const referencing = index.getReferencingNotes(targetFname);
          const locations: vscode.Location[] = [];

          for (const srcNote of referencing) {
            let raw: string;
            try {
              raw = await fs.promises.readFile(srcNote.fsPath, "utf8");
            } catch {
              continue;
            }
            const srcLinks = extractWikilinks(raw, 0);
            const uri = vscode.Uri.file(srcNote.fsPath);
            for (const l of srcLinks) {
              if (l.target.toLowerCase() !== targetKey) continue;
              const startPos = offsetToPosition(raw, l.start);
              const endPos = offsetToPosition(raw, l.end);
              locations.push(new vscode.Location(uri, new vscode.Range(startPos, endPos)));
            }
          }
          return locations;
        },
      })
    );

    // 5. Backlinks CodeLens at top of vault Markdown notes (subtle, clickable)
    context.subscriptions.push(
      vscode.languages.registerCodeLensProvider(mdSelector, {
        onDidChangeCodeLenses: this._onDidChangeCodeLenses.event,
        provideCodeLenses: (document) => {
          const enabled = vscode.workspace
            .getConfiguration("sailzen")
            .get<boolean>("editor.showBacklinksCodeLens", true);
          if (!enabled) return [];

          const index = this.state.vaultIndex;
          if (!index) return [];
          const fname = this.state.getNoteFnameForPath(document.uri.fsPath);
          if (!fname) return [];

          const refs = index.getReferencingNotes(fname).filter(
            (r) => r.fname.toLowerCase() !== fname.toLowerCase()
          );
          const count = refs.length;
          const label =
            count === 0
              ? "$(references) 0 backlinks"
              : count === 1
              ? "$(references) 1 backlink"
              : `$(references) ${count} backlinks`;

          const topRange = new vscode.Range(0, 0, 0, 0);
          return [
            new vscode.CodeLens(topRange, {
              title: label,
              tooltip:
                count > 0
                  ? `Show ${count} note(s) linking to ${fname}`
                  : `No other notes link to ${fname} yet`,
              command: "sailzen.showBacklinks",
              arguments: [fname],
            }),
          ];
        },
      })
    );

    // 6. Lightweight Hover preview for [[wikilinks]], ![[embeds]], [[#anchors]], & Story Bible
    context.subscriptions.push(
      vscode.languages.registerHoverProvider(mdSelector, {
        provideHover: async (document, position) => {
          const index = this.state.vaultIndex;
          if (!index) return undefined;
          const offset = document.offsetAt(position);
          const links = extractWikilinks(document.getText(), 0);
          const hit = links.find((l) => offset >= l.start && offset <= l.end);
          if (!hit) return undefined;

          const md = new vscode.MarkdownString();
          md.isTrusted = true;

          // Same-file heading anchor preview
          if (!hit.target && hit.anchor) {
            const parsedCur = parseNoteContent("current", document.getText());
            const section = extractHeadingSection(parsedCur.body, hit.anchor);
            md.appendMarkdown(`### § ${hit.anchor}\n`);
            if (section) {
              md.appendMarkdown(`\n---\n\n${section.split(/\r?\n/).slice(0, 12).join("\n").slice(0, 500)}`);
            } else {
              md.appendMarkdown(`*(heading not found in current document)*`);
            }
            return new vscode.Hover(md);
          }

          const target = index.getNote(hit.target);
          const cloudNoteItem = !this.state.privacyGuard.isWorkOfflineActive()
            ? this.state.findNoteItem(hit.target) ||
              (hit.alias ? this.state.findNoteItem(hit.alias) : undefined)
            : undefined;

          if (!target && cloudNoteItem) {
            const niTitle =
              cloudNoteItem.title || cloudNoteItem.slug || `NoteItem #${cloudNoteItem.id}`;
            md.appendMarkdown(`### 📖 ${niTitle} *(${cloudNoteItem.category})*\n`);
            md.appendMarkdown(`Cloud Story Bible · \`${cloudNoteItem.setting_file}\`\n\n`);
            try {
              const contentRes = await this.state.apiClient.getNoteItemContent(cloudNoteItem.id);
              const excerpt = (contentRes.content || "")
                .replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, "")
                .trim()
                .split(/\r?\n/)
                .slice(0, 10)
                .join("\n")
                .slice(0, 500);
              if (excerpt) {
                md.appendMarkdown(`---\n\n${excerpt}\n\n`);
              }
            } catch {
              // ignore fetch failure
            }
            const openArgs = encodeURIComponent(
              JSON.stringify([SailZenVfsUri.noteItem(cloudNoteItem.id, niTitle)])
            );
            md.appendMarkdown(
              `[Open Full Story Bible Card](command:sailzen.openVirtualUri?${openArgs})`
            );
            return new vscode.Hover(md);
          }

          if (!target) {
            md.appendMarkdown(
              `**${hit.target}** *(note does not exist yet — Ctrl+Click or Alt+Enter to create)*`
            );
            return new vscode.Hover(md);
          }

          md.appendMarkdown(`### ${target.title}${hit.isEmbed ? " *(embed)*" : ""}\n`);
          md.appendMarkdown(`\`${target.fname}\``);
          if (hit.anchor) {
            md.appendMarkdown(` § \`#${hit.anchor}\``);
          }
          if (target.tags.length > 0) {
            md.appendMarkdown(` · ${target.tags.map((t) => `#${t}`).join(" ")}`);
          }
          try {
            const raw = await fs.promises.readFile(target.fsPath, "utf8");
            const parsed = parseNoteContent(target.fname, raw);
            const baseBody = hit.anchor
              ? extractHeadingSection(parsed.body, hit.anchor) ?? parsed.body
              : parsed.body;
            const snippet = baseBody
              .trim()
              .split(/\r?\n/)
              .slice(0, 12)
              .join("\n")
              .slice(0, 550);
            if (snippet) {
              md.appendMarkdown(`\n\n---\n\n${snippet}`);
            }
          } catch {
            // ignore preview read error
          }
          if (cloudNoteItem) {
            const niTitle =
              cloudNoteItem.title || cloudNoteItem.slug || `NoteItem #${cloudNoteItem.id}`;
            const openArgs = encodeURIComponent(
              JSON.stringify([SailZenVfsUri.noteItem(cloudNoteItem.id, niTitle)])
            );
            md.appendMarkdown(
              `\n\n---\n\n📖 Linked Cloud Story Bible: [${niTitle} (${cloudNoteItem.category})](command:sailzen.openVirtualUri?${openArgs})`
            );
          }
          return new vscode.Hover(md);
        },
      })
    );

    // 7. Live native Markdown Editor decorations for [[wikilinks]], ![[embeds]], & repo:// links
    context.subscriptions.push(
      vscode.window.onDidChangeActiveTextEditor((editor) => {
        if (editor) this.scheduleDecorate(editor);
      }),
      vscode.workspace.onDidChangeTextDocument((e) => {
        const active = vscode.window.activeTextEditor;
        if (active && active.document === e.document) {
          this.scheduleDecorate(active);
        }
      }),
      this.state.onDidVaultChange(() => {
        this._onDidChangeCodeLenses.fire();
        for (const ed of vscode.window.visibleTextEditors) {
          this.decorateEditor(ed);
        }
      }),
      vscode.workspace.onDidChangeConfiguration((e) => {
        if (
          e.affectsConfiguration("sailzen.editor.decorateWikilinks") ||
          e.affectsConfiguration("sailzen.editor.showBacklinksCodeLens")
        ) {
          this._onDidChangeCodeLenses.fire();
          for (const ed of vscode.window.visibleTextEditors) {
            this.decorateEditor(ed);
          }
        }
      })
    );

    // Decorate already-visible markdown editors immediately
    for (const ed of vscode.window.visibleTextEditors) {
      this.decorateEditor(ed);
    }
  }

  /** Keyboard-driven jump/create for [[wikilink]], ![[embed]], [[#anchor]], or repo:// link under cursor. */
  async followLinkAtCursor(editor: vscode.TextEditor): Promise<boolean> {
    const doc = editor.document;
    const text = doc.getText();
    const offset = doc.offsetAt(editor.selection.active);

    // 1. Check [[wikilink]] / ![[embed]] / [[#anchor]]
    const links = extractWikilinks(text, 0);
    const hit = links.find((l) => offset >= l.start && offset <= l.end);
    if (hit) {
      if (!hit.target && hit.anchor) {
        return this.jumpToLocalHeading(hit.anchor, doc.uri.fsPath);
      }
      await this.state.openOrCreateNote(hit.target, { anchor: hit.anchor });
      return true;
    }

    // 2. Check repo://<slug>/<relPath>#L<line>
    REPO_LINK_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = REPO_LINK_RE.exec(text)) !== null) {
      if (offset >= m.index && offset <= m.index + m[0].length) {
        await this.openRepoLink({
          slug: m[1],
          relPath: m[2],
          line: m[3] ? Number(m[3]) : undefined,
        });
        return true;
      }
    }

    return false;
  }

  private async jumpToLocalHeading(anchor: string, sourceFsPath?: string): Promise<boolean> {
    let editor = vscode.window.activeTextEditor;
    if (
      sourceFsPath &&
      (!editor || editor.document.uri.fsPath.toLowerCase() !== sourceFsPath.toLowerCase())
    ) {
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(sourceFsPath));
      editor = await vscode.window.showTextDocument(doc, { preview: false });
    }
    if (!editor) return false;
    const line = findHeadingLine(editor.document.getText(), anchor);
    if (line === undefined) {
      vscode.window.showInformationMessage(`SailZen: Heading "#${anchor}" not found in this note.`);
      return false;
    }
    const pos = new vscode.Position(line, 0);
    editor.selection = new vscode.Selection(pos, pos);
    editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
    return true;
  }

  private async openRepoLink(args: { slug: string; relPath: string; line?: number }): Promise<void> {
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

  private scheduleDecorate(editor: vscode.TextEditor): void {
    if (editor.document.languageId !== "markdown") return;
    if (this.decorateTimer) clearTimeout(this.decorateTimer);
    this.decorateTimer = setTimeout(() => {
      this.decorateTimer = null;
      this.decorateEditor(editor);
    }, 60);
  }

  private decorateEditor(editor: vscode.TextEditor): void {
    if (editor.document.languageId !== "markdown" || editor.document.uri.scheme !== "file") {
      return;
    }

    const enabled = vscode.workspace
      .getConfiguration("sailzen")
      .get<boolean>("editor.decorateWikilinks", true);
    if (!enabled) {
      editor.setDecorations(this.existingLinkDecoration, []);
      editor.setDecorations(this.missingLinkDecoration, []);
      editor.setDecorations(this.embedLinkDecoration, []);
      editor.setDecorations(this.repoLinkDecoration, []);
      return;
    }

    const text = editor.document.getText();
    const index = this.state.vaultIndex;
    const existingRanges: vscode.Range[] = [];
    const missingRanges: vscode.Range[] = [];
    const embedRanges: vscode.Range[] = [];
    const repoRanges: vscode.Range[] = [];

    for (const wl of extractWikilinks(text, 0)) {
      const range = new vscode.Range(
        editor.document.positionAt(wl.start),
        editor.document.positionAt(wl.end)
      );
      if (wl.isEmbed) {
        embedRanges.push(range);
      } else if (!wl.target && wl.anchor) {
        existingRanges.push(range);
      } else if (!index || index.getNote(wl.target)) {
        existingRanges.push(range);
      } else {
        missingRanges.push(range);
      }
    }

    REPO_LINK_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = REPO_LINK_RE.exec(text)) !== null) {
      repoRanges.push(
        new vscode.Range(
          editor.document.positionAt(m.index),
          editor.document.positionAt(m.index + m[0].length)
        )
      );
    }

    editor.setDecorations(this.existingLinkDecoration, existingRanges);
    editor.setDecorations(this.missingLinkDecoration, missingRanges);
    editor.setDecorations(this.embedLinkDecoration, embedRanges);
    editor.setDecorations(this.repoLinkDecoration, repoRanges);
  }
}

/** Convert a 0-based character offset in `text` to a VS Code Position without opening a TextDocument. */
function offsetToPosition(text: string, offset: number): vscode.Position {
  const clamped = Math.max(0, Math.min(offset, text.length));
  let line = 0;
  let lastNl = -1;
  for (let i = 0; i < clamped; i++) {
    if (text.charCodeAt(i) === 10) {
      line++;
      lastNl = i;
    }
  }
  return new vscode.Position(line, clamped - lastNl - 1);
}
