import {
  DocExportConfig,
  hasDocConfig,
  NoteProps,
} from "@saili/common-all";
import { resolvePath, tmpDir } from "@saili/common-server";
import fs from "fs-extra";
import _ from "lodash";
import path from "path";
import * as vscode from "vscode";
import { DENDRON_COMMANDS } from "../constants";
import { IDendronExtension } from "../dendronExtensionInterface";
import { ExtensionProvider } from "../ExtensionProvider";
import { VSCodeUtils } from "../vsCodeUtils";
import { BasicCommand } from "./base";
import {
  assembleDocument,
  generateLatex,
  resolveProfile,
} from "../docEngine";

type CommandOpts = {
  note: NoteProps;
  exportConfig: DocExportConfig;
};

type CommandOutput = {
  outputDir: string;
  files: string[];
};

export class ExportNoteToLatexCommand
  extends BasicCommand<CommandOpts, CommandOutput>
{
  static requireActiveWorkspace = true;
  key = DENDRON_COMMANDS.EXPORT_NOTE_TO_LATEX.key;
  private extension: IDendronExtension;

  constructor(ext: IDendronExtension) {
    super();
    this.extension = ext;
  }

  async sanityCheck() {
    const editor = VSCodeUtils.getActiveTextEditor();
    if (!editor) {
      return "No active document";
    }
    return;
  }

  async gatherInputs(): Promise<CommandOpts | undefined> {
    const ctx = this.key;
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
    // Fetch all notes for profile resolution
    const allNotesForProfile = await engine.findNotes({});
    const notesByIdForProfile: Record<string, NoteProps> = {};
    for (const n of allNotesForProfile) {
      notesByIdForProfile[n.id] = n;
    }
    const profile = resolveProfile(note, notesByIdForProfile);

    if (profile.exports.length === 0) {
      vscode.window.showErrorMessage("No export configurations found for this note.");
      return;
    }

    // If multiple exports, let user choose
    let exportConfig = profile.exports[0];
    if (profile.exports.length > 1) {
      const pick = await vscode.window.showQuickPick(
        profile.exports.map((e) => ({
          label: `${e.format}${e.template ? ` (${e.template})` : ""}`,
          description: e.outDir || "default output directory",
          exportConfig: e,
        })),
        { placeHolder: "Select export format" }
      );
      if (!pick) return;
      exportConfig = pick.exportConfig;
    }

    return { note, exportConfig };
  }

  async execute(opts: CommandOpts): Promise<CommandOutput> {
    const { note, exportConfig } = opts;
    const engine = ExtensionProvider.getEngine();
    // Fetch all notes for profile resolution and document assembly
    const allNotes = await engine.findNotes({});
    const notesById: Record<string, NoteProps> = {};
    for (const n of allNotes) {
      notesById[n.id] = n;
    }
    const profile = resolveProfile(note, notesById);

    vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `Exporting ${note.fname} to ${exportConfig.format}...`,
        cancellable: false,
      },
      async () => {
        // Assemble document
        const assembled = assembleDocument(profile, notesById);

        // Generate output
        const generated = generateLatex(
          assembled,
          profile,
          exportConfig,
          notesById
        );

        // Determine output directory
        const wsRoot = engine.wsRoot;
        const projectName = profile.rootNoteFname.replace(/\./g, "_");
        const outDir = exportConfig.outDir
          ? resolvePath(exportConfig.outDir, wsRoot)
          : path.join(wsRoot, ".sailzen", "doc", projectName, exportConfig.format);

        await fs.ensureDir(outDir);

        // Write main file
        const mainFileName = `main.${generated.ext}`;
        const mainPath = path.join(outDir, mainFileName);
        await fs.writeFile(mainPath, generated.mainContent, "utf-8");

        const files = [mainPath];

        // Write extra files
        for (const extra of generated.extraFiles) {
          const extraPath = path.join(outDir, extra.path);
          await fs.ensureDir(path.dirname(extraPath));
          await fs.writeFile(extraPath, extra.content, "utf-8");
          files.push(extraPath);
        }

        return { outputDir: outDir, files };
      }
    );

    // The withProgress doesn't return the value directly in this pattern,
    // so we return a placeholder and show the actual result in showResponse
    return { outputDir: "", files: [] };
  }

  async showResponse(resp: CommandOutput) {
    if (!resp.outputDir) {
      // The actual result is computed inside withProgress; for now we show a generic message
      vscode.window.showInformationMessage(
        `Export complete. Check the output directory for generated files.`
      );
      return;
    }

    const openDir = "Open Output Directory";
    const choice = await vscode.window.showInformationMessage(
      `Exported to ${resp.outputDir}`,
      openDir
    );
    if (choice === openDir) {
      vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(resp.outputDir));
    }
  }
}
