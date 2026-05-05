import {
  DocExportConfig,
  hasDocConfig,
  NoteProps,
} from "@saili/common-all";
import { resolvePath } from "@saili/common-server";
import fs from "fs-extra";
import path from "path";
import * as vscode from "vscode";
import { DENDRON_COMMANDS } from "../constants";
import { IDendronExtension } from "../dendronExtensionInterface";
import { ExtensionProvider } from "../ExtensionProvider";
import { Logger } from "../logger";
import { VSCodeUtils } from "../vsCodeUtils";
import { BasicCommand } from "./base";
import {
  assembleDocument,
  generateMarkdown,
  resolveProfile,
} from "../docEngine";

type CommandOpts = {
  note: NoteProps;
  exportConfig: DocExportConfig;
};

type CommandOutput = {
  outputPath: string;
  content: string;
};

export class ExportNoteToMarkdownCommand extends BasicCommand<
  CommandOpts,
  CommandOutput
> {
  static requireActiveWorkspace = true;
  key = DENDRON_COMMANDS.EXPORT_NOTE_TO_MARKDOWN.key;
  private extension: IDendronExtension;

  constructor(ext: IDendronExtension) {
    super();
    this.extension = ext;
  }

  async sanityCheck() {
    if (!VSCodeUtils.getActiveTextEditor()) {
      return "No active document";
    }
    return;
  }

  async gatherInputs(): Promise<CommandOpts | undefined> {
    const editor = VSCodeUtils.getActiveTextEditor();
    if (!editor) return;

    const note = await ExtensionProvider.getWSUtils().getNoteFromDocument(
      editor.document
    );
    if (!note) {
      vscode.window.showErrorMessage("Could not find note for current document");
      return;
    }

    if (!hasDocConfig(note.custom)) {
      vscode.window.showWarningMessage(
        "Current note does not have a `doc` frontmatter configuration."
      );
    }

    const engine = ExtensionProvider.getEngine();
    const allNotes = await engine.findNotes({ excludeStub: false });
    const notesById: Record<string, NoteProps> = {};
    for (const n of allNotes) {
      notesById[n.id] = n;
    }
    const profile = resolveProfile(note, notesById);

    const markdownExports = profile.exports.filter(
      (e) => e.format === "markdown"
    );

    let exportConfig: DocExportConfig;
    if (markdownExports.length > 0) {
      exportConfig = markdownExports[0];
    } else {
      exportConfig = { format: "markdown" };
    }

    return { note, exportConfig };
  }

  async execute(opts: CommandOpts): Promise<CommandOutput> {
    const { note, exportConfig } = opts;
    const engine = ExtensionProvider.getEngine();

    const allNotes = await engine.findNotes({ excludeStub: false });
    const notesById: Record<string, NoteProps> = {};
    for (const n of allNotes) {
      notesById[n.id] = n;
    }

    return vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `Exporting ${note.fname} to Markdown…`,
        cancellable: false,
      },
      async () => {
        const profile = resolveProfile(note, notesById);
        const assembled = assembleDocument(profile, notesById);

        const generated = await generateMarkdown(
          assembled,
          profile,
          exportConfig,
          notesById,
          engine.wsRoot
        );

        Logger.info({
          ctx: `${this.key}:execute`,
          msg: "generateMarkdown completed",
          unresolvedRefs: assembled.unresolvedRefs,
        });

        const wsRoot = engine.wsRoot;
        const projectName = profile.rootNoteFname.replace(/\./g, "_");
        const outDir = exportConfig.outDir
          ? resolvePath(exportConfig.outDir, wsRoot)
          : path.join(wsRoot, ".sailzen", "doc", projectName, "markdown");

        await fs.ensureDir(outDir);

        const outputPath = path.join(outDir, "export.md");
        await fs.writeFile(outputPath, generated.mainContent, "utf-8");

        Logger.info({
          ctx: `${this.key}:execute`,
          msg: "markdown export complete",
          outputPath,
        });

        if (assembled.unresolvedRefs.length > 0) {
          vscode.window.showWarningMessage(
            `Export complete with ${assembled.unresolvedRefs.length} unresolved reference(s): ${assembled.unresolvedRefs.slice(0, 3).join(", ")}${assembled.unresolvedRefs.length > 3 ? "…" : ""}`
          );
        }

        return { outputPath, content: generated.mainContent };
      }
    );
  }

  async showResponse(resp: CommandOutput) {
    const openFile = "Open File";
    const copyClipboard = "Copy to Clipboard";

    const choice = await vscode.window.showInformationMessage(
      `Markdown exported to ${resp.outputPath}`,
      openFile,
      copyClipboard
    );

    if (choice === openFile) {
      const doc = await vscode.workspace.openTextDocument(
        vscode.Uri.file(resp.outputPath)
      );
      await vscode.window.showTextDocument(doc);
    } else if (choice === copyClipboard) {
      await vscode.env.clipboard.writeText(resp.content);
      vscode.window.showInformationMessage("Markdown copied to clipboard.");
    }
  }
}
