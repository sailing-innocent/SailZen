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
import { Logger } from "../logger";
import { VSCodeUtils } from "../vsCodeUtils";
import { BasicCommand } from "./base";
import {
  assembleDocument,
  generateLatex,
  resolveProfile,
  listBuiltinTemplates,
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
    const allNotesForProfile = await engine.findNotes({ excludeStub: false });
    Logger.info({
      ctx: `${this.key}:gatherInputs`,
      msg: `findNotes({excludeStub: false}) returned ${allNotesForProfile.length} notes`,
      noteIds: allNotesForProfile.map((n) => n.id),
      targetNoteId: note.id,
    });
    const notesByIdForProfile: Record<string, NoteProps> = {};
    for (const n of allNotesForProfile) {
      notesByIdForProfile[n.id] = n;
    }
    const profile = resolveProfile(note, notesByIdForProfile);

    // If no exports defined, let user pick from built-in templates
    let exportConfig: DocExportConfig;
    if (profile.exports.length === 0) {
      const templates = listBuiltinTemplates("latex");
      const pick = await vscode.window.showQuickPick(
        templates.map((t) => ({
          label: t.id,
          description: t.description,
          templateId: t.id,
        })),
        { placeHolder: "Select LaTeX template" }
      );
      if (!pick) return;
      exportConfig = { format: "latex", template: pick.templateId };
    } else if (profile.exports.length > 1) {
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
    } else {
      exportConfig = profile.exports[0];
    }

    return { note, exportConfig };
  }

  async execute(opts: CommandOpts): Promise<CommandOutput> {
    const { note, exportConfig } = opts;
    const engine = ExtensionProvider.getEngine();
    // Fetch all notes for profile resolution and document assembly
    const allNotes = await engine.findNotes({ excludeStub: false });
    Logger.info({
      ctx: `${this.key}:execute`,
      msg: `findNotes({excludeStub: false}) returned ${allNotes.length} notes`,
      noteIds: allNotes.map((n) => n.id),
      targetNoteId: note.id,
    });
    const notesById: Record<string, NoteProps> = {};
    for (const n of allNotes) {
      notesById[n.id] = n;
    }
    const profile = resolveProfile(note, notesById);

    return vscode.window.withProgress(
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
          notesById,
          engine.wsRoot
        );
        // eslint-disable-next-line no-console
        console.log("[ExportNoteToLatexCommand] generateLatex done, assetFiles=", generated.assetFiles);
        Logger.info({
          ctx: `${this.key}:execute`,
          msg: "generateLatex completed",
          assetFilesCount: generated.assetFiles.length,
          assetFiles: generated.assetFiles.map((a) => ({
            srcPath: a.srcPath,
            destPath: a.destPath,
          })),
        });

        // Determine output directories
        // Project-level shared dir (for figures, etc. across formats)
        const wsRoot = engine.wsRoot;
        const projectName = profile.rootNoteFname.replace(/\./g, "_");
        const projectDir = exportConfig.outDir
          ? resolvePath(exportConfig.outDir, wsRoot)
          : path.join(wsRoot, ".sailzen", "doc", projectName);
        // Format-specific dir (latex/ typst/ slidev/)
        const outDir = path.join(projectDir, exportConfig.format);

        Logger.info({
          ctx: `${this.key}:execute`,
          msg: "output directories resolved",
          wsRoot,
          projectDir,
          outDir,
          projectName,
        });

        await fs.ensureDir(outDir);

        // Write main file
        const mainFileName = `main.${generated.ext}`;
        const mainPath = path.join(outDir, mainFileName);
        await fs.writeFile(mainPath, generated.mainContent, "utf-8");
        Logger.info({
          ctx: `${this.key}:execute`,
          msg: `main file written: ${mainPath}`,
        });

        const files = [mainPath];

        // Write extra files
        for (const extra of generated.extraFiles) {
          const extraPath = path.join(outDir, extra.path);
          await fs.ensureDir(path.dirname(extraPath));
          await fs.writeFile(extraPath, extra.content, "utf-8");
          files.push(extraPath);
          Logger.info({
            ctx: `${this.key}:execute`,
            msg: `extra file written: ${extraPath}`,
          });
        }

        // Write section files if split mode is enabled
        if (generated.sections && generated.sections.length > 0) {
          const sectionsDir = path.join(outDir, "sections");
          await fs.ensureDir(sectionsDir);
          for (const section of generated.sections) {
            const sectionPath = path.join(sectionsDir, section.fileName);
            await fs.writeFile(sectionPath, section.content, "utf-8");
            files.push(sectionPath);
            Logger.info({
              ctx: `${this.key}:execute`,
              msg: `section file written: ${sectionPath}`,
            });
          }
        }

        // Copy asset files (images) to project-level shared figures/ directory
        // so that latex, typst, slidev can all reference the same images.
        // eslint-disable-next-line no-console
        console.log("[ExportNoteToLatexCommand] starting asset copy, count=", generated.assetFiles.length, "projectDir=", projectDir);
        Logger.info({
          ctx: `${this.key}:execute`,
          msg: `starting asset copy, count=${generated.assetFiles.length}`,
        });
        for (const asset of generated.assetFiles) {
          const assetDestPath = path.join(projectDir, asset.destPath);
          const srcExists = await fs.pathExists(asset.srcPath);
          // eslint-disable-next-line no-console
          console.log("[ExportNoteToLatexCommand] asset copy item:", { srcPath: asset.srcPath, destPath: assetDestPath, srcExists });
          Logger.info({
            ctx: `${this.key}:execute`,
            msg: `processing asset copy`,
            srcPath: asset.srcPath,
            destPath: assetDestPath,
            srcExists,
          });
          await fs.ensureDir(path.dirname(assetDestPath));
          if (srcExists) {
            try {
              await fs.copy(asset.srcPath, assetDestPath);
              files.push(assetDestPath);
              // eslint-disable-next-line no-console
              console.log("[ExportNoteToLatexCommand] asset copied OK:", assetDestPath);
              Logger.info({
                ctx: `${this.key}:execute`,
                msg: `asset copied successfully`,
                srcPath: asset.srcPath,
                destPath: assetDestPath,
              });
            } catch (copyErr: any) {
              // eslint-disable-next-line no-console
              console.error("[ExportNoteToLatexCommand] asset copy FAILED:", copyErr.message);
              Logger.error({
                ctx: `${this.key}:execute`,
                msg: `asset copy failed`,
                srcPath: asset.srcPath,
                destPath: assetDestPath,
                error: copyErr.message,
              });
            }
          } else {
            // eslint-disable-next-line no-console
            console.warn("[ExportNoteToLatexCommand] asset src NOT FOUND:", asset.srcPath);
            Logger.warn({
              ctx: `${this.key}:execute`,
              msg: `Asset file not found: ${asset.srcPath}`,
            });
          }
        }

        Logger.info({
          ctx: `${this.key}:execute`,
          msg: "export complete",
          outputDir: outDir,
          filesWritten: files,
        });

        return { outputDir: outDir, files };
      }
    );
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
