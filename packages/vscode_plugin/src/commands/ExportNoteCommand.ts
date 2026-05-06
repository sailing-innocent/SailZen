import {
  DocExportConfig,
  DocExportFormat,
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
  generateLatex,
  generateTypst,
  generateMarkdown,
  resolveProfile,
  listTemplates,
} from "../docEngine";

// ============================================================================
// Types
// ============================================================================

type CommandOpts = {
  note: NoteProps;
  exportConfig: DocExportConfig;
};

type CommandOutput = {
  outputDir: string;
  files: string[];
};

// ============================================================================
// Format display labels
// ============================================================================

const FORMAT_LABELS: Record<DocExportFormat, string> = {
  latex: "LaTeX",
  typst: "Typst",
  slidev: "Slidev (Markdown)",
  markdown: "Markdown",
};

const FORMAT_ICONS: Record<DocExportFormat, string> = {
  latex: "$(file-code)",
  typst: "$(symbol-file)",
  slidev: "$(play)",
  markdown: "$(markdown)",
};

// ============================================================================
// ExportNoteCommand - unified export command for all formats
// ============================================================================

export class ExportNoteCommand extends BasicCommand<CommandOpts, CommandOutput> {
  static requireActiveWorkspace = true;
  key = DENDRON_COMMANDS.EXPORT_NOTE.key;
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
        "Current note does not have a `doc` frontmatter configuration. Using defaults."
      );
    }

    const engine = ExtensionProvider.getEngine();
    const allNotes = await engine.findNotes({ excludeStub: false });
    Logger.info({
      ctx: `${this.key}:gatherInputs`,
      msg: `findNotes returned ${allNotes.length} notes`,
      targetNoteId: note.id,
    });

    const notesById: Record<string, NoteProps> = {};
    for (const n of allNotes) {
      notesById[n.id] = n;
    }
    const profile = resolveProfile(note, notesById);
    const wsRoot = engine.wsRoot;

    // -------------------------------------------------------------------------
    // Step 1: Determine the export config from frontmatter or user selection
    // -------------------------------------------------------------------------
    let exportConfig: DocExportConfig | undefined;

    if (profile.exports.length === 0) {
      // No exports configured — let user pick format + template from scratch
      exportConfig = await this._pickFormatAndTemplate(wsRoot);
    } else if (profile.exports.length === 1) {
      // Single export configured — confirm with the user
      exportConfig = await this._confirmSingleExport(profile.exports[0], wsRoot);
    } else {
      // Multiple exports configured — let user choose one
      exportConfig = await this._pickFromConfiguredExports(profile.exports, wsRoot);
    }

    if (!exportConfig) return;

    return { note, exportConfig };
  }

  // ---------------------------------------------------------------------------
  // Case A: No exports in frontmatter → full format + template picker
  // ---------------------------------------------------------------------------
  private async _pickFormatAndTemplate(wsRoot: string): Promise<DocExportConfig | undefined> {
    const ALL_FORMATS: DocExportFormat[] = ["latex", "typst", "markdown", "slidev"];

    const formatPick = await vscode.window.showQuickPick(
      ALL_FORMATS.map((fmt) => ({
        label: `${FORMAT_ICONS[fmt]}  ${FORMAT_LABELS[fmt]}`,
        description: fmt,
        format: fmt,
      })),
      {
        placeHolder: "Select export format",
        title: "Export Note — Choose Format",
      }
    );
    if (!formatPick) return;

    const format = formatPick.format;
    return this._pickTemplate(format, { format }, wsRoot);
  }

  // ---------------------------------------------------------------------------
  // Case B: Single export in frontmatter → confirm and optionally switch template
  // ---------------------------------------------------------------------------
  private async _confirmSingleExport(
    configured: DocExportConfig,
    wsRoot: string
  ): Promise<DocExportConfig | undefined> {
    const formatLabel = FORMAT_LABELS[configured.format] ?? configured.format;
    const templateInfo = configured.template ? ` · template: ${configured.template}` : "";
    const outDirInfo = configured.outDir ? ` · outDir: ${configured.outDir}` : "";

    const USE_CONFIG = "Use configured export";
    const PICK_TEMPLATE = "Change template…";
    const CANCEL = "Cancel";

    const choice = await vscode.window.showQuickPick(
      [
        {
          label: `$(check)  ${USE_CONFIG}`,
          description: `${formatLabel}${templateInfo}${outDirInfo}`,
          value: USE_CONFIG,
        },
        {
          label: `$(list-unordered)  ${PICK_TEMPLATE}`,
          description: `Browse available ${formatLabel} templates`,
          value: PICK_TEMPLATE,
        },
        {
          label: `$(x)  ${CANCEL}`,
          description: "",
          value: CANCEL,
        },
      ],
      {
        placeHolder: `Export as ${formatLabel}`,
        title: "Export Note — Confirm Configuration",
      }
    );

    if (!choice || choice.value === CANCEL) return;
    if (choice.value === USE_CONFIG) return configured;

    // User wants to pick a different template
    return this._pickTemplate(configured.format, configured, wsRoot);
  }

  // ---------------------------------------------------------------------------
  // Case C: Multiple exports in frontmatter → pick one (with optional template override)
  // ---------------------------------------------------------------------------
  private async _pickFromConfiguredExports(
    exports: DocExportConfig[],
    wsRoot: string
  ): Promise<DocExportConfig | undefined> {
    const items = exports.map((e, idx) => {
      const formatLabel = FORMAT_LABELS[e.format] ?? e.format;
      const templateInfo = e.template ? ` (${e.template})` : "";
      const outDirInfo = e.outDir ? ` → ${e.outDir}` : "";
      return {
        label: `${FORMAT_ICONS[e.format]}  ${formatLabel}${templateInfo}`,
        description: `config #${idx + 1}${outDirInfo}`,
        exportConfig: e,
      };
    });

    // Add "pick template manually" option at the bottom
    const PICK_NEW = "$(add)  Choose a different format / template…";
    const allItems: (typeof items[number] | { label: string; description: string; exportConfig: null })[] = [
      ...items,
      { label: PICK_NEW, description: "", exportConfig: null },
    ];

    const pick = await vscode.window.showQuickPick(allItems, {
      placeHolder: "Select export configuration",
      title: "Export Note — Select Format",
    });

    if (!pick) return;

    if (pick.exportConfig === null) {
      // User chose to pick manually
      return this._pickFormatAndTemplate(wsRoot);
    }

    // Ask whether to use as-is or override template
    return this._confirmSingleExport(pick.exportConfig, wsRoot);
  }

  // ---------------------------------------------------------------------------
  // Template picker for a given format
  // ---------------------------------------------------------------------------
  private async _pickTemplate(
    format: DocExportFormat,
    base: Partial<DocExportConfig>,
    wsRoot: string
  ): Promise<DocExportConfig | undefined> {
    // markdown and slidev have no real template system — return as-is
    if (format === "markdown" || format === "slidev") {
      return { ...base, format } as DocExportConfig;
    }

    const templates = await listTemplates(format, wsRoot);
    if (templates.length === 0) {
      // No templates available — use format without template
      return { ...base, format } as DocExportConfig;
    }

    const pick = await vscode.window.showQuickPick(
      [
        {
          label: "$(symbol-misc)  (no template)",
          description: "Use default format output without a template",
          templateId: undefined as string | undefined,
        },
        ...templates.map((t) => ({
          label: `$(file-code)  ${t.id}`,
          description: t.description,
          templateId: t.id,
        })),
      ],
      {
        placeHolder: `Select ${FORMAT_LABELS[format]} template`,
        title: `Export Note — ${FORMAT_LABELS[format]} Template`,
      }
    );

    if (!pick) return;
    const result: DocExportConfig = { ...base, format } as DocExportConfig;
    if (pick.templateId) {
      result.template = pick.templateId;
    } else {
      delete result.template;
    }
    return result;
  }

  // ---------------------------------------------------------------------------
  // Execute: dispatch to the correct backend
  // ---------------------------------------------------------------------------
  async execute(opts: CommandOpts): Promise<CommandOutput> {
    const { note, exportConfig } = opts;
    const engine = ExtensionProvider.getEngine();
    const allNotes = await engine.findNotes({ excludeStub: false });
    Logger.info({
      ctx: `${this.key}:execute`,
      msg: `findNotes returned ${allNotes.length} notes`,
      targetNoteId: note.id,
      format: exportConfig.format,
    });

    const notesById: Record<string, NoteProps> = {};
    for (const n of allNotes) {
      notesById[n.id] = n;
    }
    const profile = resolveProfile(note, notesById);
    const formatLabel = FORMAT_LABELS[exportConfig.format] ?? exportConfig.format;

    return vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `Exporting ${note.fname} to ${formatLabel}…`,
        cancellable: false,
      },
      async () => {
        const assembled = assembleDocument(profile, notesById);
        const wsRoot = engine.wsRoot;
        const projectName = profile.rootNoteFname.replace(/\./g, "_");

        // Project-level shared dir (figures shared across formats)
        const projectDir = exportConfig.outDir
          ? resolvePath(exportConfig.outDir, wsRoot)
          : path.join(wsRoot, ".sailzen", "doc", projectName);

        // Format-specific subdirectory
        const outDir = path.join(projectDir, exportConfig.format);
        await fs.ensureDir(outDir);

        Logger.info({
          ctx: `${this.key}:execute`,
          msg: "directories resolved",
          projectDir,
          outDir,
        });

        const files: string[] = [];

        // ------------------------------------------------------------------
        // Dispatch to format backend
        // ------------------------------------------------------------------
        switch (exportConfig.format) {
          case "latex": {
            const generated = await generateLatex(
              assembled,
              profile,
              exportConfig,
              notesById,
              wsRoot
            );
            Logger.info({ ctx: `${this.key}:execute`, msg: "latex backend done" });
            await this._writeGeneratedFiles(generated, outDir, projectDir, files);
            break;
          }

          case "typst": {
            const generated = await generateTypst(
              assembled,
              profile,
              exportConfig,
              notesById,
              wsRoot
            );
            Logger.info({ ctx: `${this.key}:execute`, msg: "typst backend done" });
            await this._writeGeneratedFiles(generated, outDir, projectDir, files);
            break;
          }

          case "markdown":
          case "slidev": {
            const generated = await generateMarkdown(
              assembled,
              profile,
              exportConfig,
              notesById,
              wsRoot
            );
            Logger.info({ ctx: `${this.key}:execute`, msg: "markdown backend done" });
            const ext = exportConfig.format === "slidev" ? "md" : "md";
            const outputPath = path.join(outDir, `export.${ext}`);
            await fs.writeFile(outputPath, generated.mainContent, "utf-8");
            files.push(outputPath);

            if (assembled.unresolvedRefs.length > 0) {
              vscode.window.showWarningMessage(
                `Export complete with ${assembled.unresolvedRefs.length} unresolved reference(s): ` +
                  `${assembled.unresolvedRefs.slice(0, 3).join(", ")}` +
                  `${assembled.unresolvedRefs.length > 3 ? "…" : ""}`
              );
            }
            break;
          }

          default:
            vscode.window.showErrorMessage(
              `Unsupported export format: ${(exportConfig as DocExportConfig).format}`
            );
            return { outputDir: outDir, files: [] };
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

  // ---------------------------------------------------------------------------
  // Write generated document files to disk (shared across latex / typst)
  // ---------------------------------------------------------------------------
  private async _writeGeneratedFiles(
    generated: Awaited<ReturnType<typeof generateLatex>>,
    outDir: string,
    projectDir: string,
    files: string[]
  ) {
    // Main file
    const mainPath = path.join(outDir, `main.${generated.ext}`);
    await fs.writeFile(mainPath, generated.mainContent, "utf-8");
    files.push(mainPath);
    Logger.info({ ctx: `${this.key}:_writeGeneratedFiles`, msg: `main written: ${mainPath}` });

    // Extra text files (.bib, latexmkrc, etc.)
    for (const extra of generated.extraFiles) {
      const extraPath = path.join(outDir, extra.path);
      await fs.ensureDir(path.dirname(extraPath));
      await fs.writeFile(extraPath, extra.content, "utf-8");
      files.push(extraPath);
    }

    // Section files (split-mode LaTeX)
    if (generated.sections && generated.sections.length > 0) {
      const sectionsDir = path.join(outDir, "sections");
      await fs.ensureDir(sectionsDir);
      for (const section of generated.sections) {
        const sectionPath = path.join(sectionsDir, section.fileName);
        await fs.writeFile(sectionPath, section.content, "utf-8");
        files.push(sectionPath);
      }
    }

    // Asset files (images) → project-level shared figures/
    for (const asset of generated.assetFiles) {
      const assetDestPath = path.join(projectDir, asset.destPath);
      const srcExists = await fs.pathExists(asset.srcPath);
      await fs.ensureDir(path.dirname(assetDestPath));
      if (srcExists) {
        try {
          await fs.copy(asset.srcPath, assetDestPath);
          files.push(assetDestPath);
        } catch (err: any) {
          Logger.error({
            ctx: `${this.key}:_writeGeneratedFiles`,
            msg: `asset copy failed: ${asset.srcPath}`,
            error: err.message,
          });
        }
      } else {
        Logger.warn({
          ctx: `${this.key}:_writeGeneratedFiles`,
          msg: `Asset file not found: ${asset.srcPath}`,
        });
      }
    }

    // Template dependency files (.cls, .sty, etc.) → format-specific output dir
    if (generated.templateFiles && generated.templateFiles.length > 0) {
      for (const tpl of generated.templateFiles) {
        const tplDestPath = path.join(outDir, tpl.destPath);
        const srcExists = await fs.pathExists(tpl.srcPath);
        await fs.ensureDir(path.dirname(tplDestPath));
        if (srcExists) {
          try {
            await fs.copy(tpl.srcPath, tplDestPath);
            files.push(tplDestPath);
          } catch (err: any) {
            Logger.error({
              ctx: `${this.key}:_writeGeneratedFiles`,
              msg: `template copy failed: ${tpl.srcPath}`,
              error: err.message,
            });
          }
        } else {
          Logger.warn({
            ctx: `${this.key}:_writeGeneratedFiles`,
            msg: `Template file not found: ${tpl.srcPath}`,
          });
        }
      }
    }
  }

  // ---------------------------------------------------------------------------
  // showResponse
  // ---------------------------------------------------------------------------
  async showResponse(resp: CommandOutput) {
    if (!resp || !resp.outputDir) {
      vscode.window.showInformationMessage("Export complete.");
      return;
    }

    const openDir = "Open Output Directory";
    const choice = await vscode.window.showInformationMessage(
      `Exported ${resp.files.length} file(s) to ${resp.outputDir}`,
      openDir
    );

    if (choice === openDir) {
      vscode.commands.executeCommand(
        "revealFileInOS",
        vscode.Uri.file(resp.outputDir)
      );
    }
  }
}
