/**
 * @file CompileDocumentCommand.ts
 * @brief Compile the most recently exported SailZen document
 * @description Invokes the appropriate build engine (latexmk/xmake/typst)
 *   for the document output in .sailzen/doc/.
 */

import * as vscode from "vscode";
import { DENDRON_COMMANDS } from "../constants";
import { IDendronExtension } from "../dendronExtensionInterface";
import { ExtensionProvider } from "../ExtensionProvider";
import { Logger } from "../logger";
import { BasicCommand } from "./base";
import {
  assembleDocument,
  assembleDocumentAST,
  astToAssembledDocument,
  generateLatex,
  generateTypst,
  resolveProfile,
  resolveProfileAST,
} from "../docEngine";
import { compileDocument, CompileResult } from "../docEngine/compileService";

type CommandOpts = {
  noteId?: string;
};

type CommandOutput = CompileResult;

export class CompileDocumentCommand extends BasicCommand<CommandOpts, CommandOutput> {
  static requireActiveWorkspace = true;
  key = DENDRON_COMMANDS.COMPILE_DOCUMENT.key;
  private extension: IDendronExtension;

  constructor(ext: IDendronExtension) {
    super();
    this.extension = ext;
  }

  async gatherInputs(): Promise<CommandOpts | undefined> {
    return {};
  }

  async execute(opts: CommandOpts): Promise<CommandOutput> {
    const engine = ExtensionProvider.getEngine();
    const wsRoot = engine.wsRoot;

    let note;
    if (opts.noteId) {
      note = (await engine.getNotesById({ ids: [opts.noteId] })).data?.[0];
    } else {
      const editor = vscode.window.activeTextEditor;
      if (editor) {
        note = await ExtensionProvider.getWSUtils().getNoteFromDocument(
          editor.document
        );
      }
    }

    if (!note) {
      vscode.window.showErrorMessage("No active document with doc profile found.");
      return { success: false, message: "No note found" };
    }

    const allNotes = await engine.findNotes({ excludeStub: false });
    const notesById: Record<string, any> = {};
    for (const n of allNotes) notesById[n.id] = n;

    const useAST = vscode.workspace
      .getConfiguration("sailzen.doc")
      .get<boolean>("useASTPipeline", true);

    let profile = resolveProfile(note, notesById);
    let assembled;
    let ast;
    if (useAST) {
      const astResult = assembleDocumentAST(profile, notesById);
      ast = astResult.ast;
      assembled = astToAssembledDocument(astResult);
      profile = resolveProfileAST(note, notesById, ast);
    } else {
      assembled = assembleDocument(profile, notesById);
    }

    const exportConfig = profile.exports[0];
    if (!exportConfig) {
      vscode.window.showErrorMessage("No export configuration found in note profile.");
      return { success: false, message: "No export config" };
    }

    const projectName = profile.rootNoteFname.replace(/\./g, "_");

    return vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `Compiling ${note.fname}…`,
        cancellable: false,
      },
      async () => {
        try {
          let generated;
          if (exportConfig.format === "latex") {
            generated = await generateLatex(
              assembled,
              profile,
              exportConfig,
              notesById,
              wsRoot,
              useAST ? { ast, useAST: true } : undefined
            );
          } else if (exportConfig.format === "typst") {
            generated = await generateTypst(
              assembled,
              profile,
              exportConfig,
              notesById,
              wsRoot
            );
          } else {
            return {
              success: false,
              message: `Compilation not supported for format: ${exportConfig.format}`,
            };
          }

          const result = await compileDocument(
            generated,
            exportConfig,
            wsRoot,
            projectName
          );

          if (result.success) {
            vscode.window.showInformationMessage(result.message);
          } else {
            vscode.window.showErrorMessage(result.message);
          }
          return result;
        } catch (err: any) {
          Logger.error({
            ctx: this.key,
            msg: "Compilation failed",
            error: err.message,
          });
          vscode.window.showErrorMessage(`Compilation failed: ${err.message}`);
          return { success: false, message: err.message };
        }
      }
    );
  }

  async showResponse(resp: CommandOutput) {
    // Response handled in execute via notifications
  }
}
