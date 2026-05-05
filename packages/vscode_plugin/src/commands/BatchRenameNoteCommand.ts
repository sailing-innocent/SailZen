import {
  DNodeProps,
  DNodeUtils,
  extractNoteChangeEntryCounts,
  NoteUtils,
} from "@saili/common-all";
import { vault2Path } from "@saili/common-server";
import fs from "fs-extra";
import _ from "lodash";
import _md from "markdown-it";
import path from "path";
import { ProgressLocation, Uri, ViewColumn, window } from "vscode";
import { DENDRON_COMMANDS } from "../constants";
import { ExtensionProvider } from "../ExtensionProvider";
import { VSCodeUtils } from "../vsCodeUtils";
import { WSUtilsV2 } from "../WSUtilsV2";
import { BasicCommand } from "./base";
import { RenameNoteOutputV2a, RenameNoteV2aCommand } from "./RenameNoteV2a";
import { IDendronExtension } from "../dendronExtensionInterface";

const md = _md();

type RenameOperation = {
  vault: any;
  oldUri: Uri;
  newUri: Uri;
};

type CommandOpts = {
  oldPrefix: string;
  newPrefix: string;
  noConfirm?: boolean;
};

type CommandOutput = RenameNoteOutputV2a & {
  operations: RenameOperation[];
};

/**
 * Batch Rename Note Command
 *
 * Renames the current note and all its children (sub-hierarchy) at once.
 * For example, if the current note is `A.B` and has children `A.B.C`, `A.B.D`,
 * renaming to `A.P` will also rename children to `A.P.C`, `A.P.D`.
 *
 * This is useful for reorganizing note hierarchies.
 */
export class BatchRenameNoteCommand extends BasicCommand<
  CommandOpts,
  CommandOutput
> {
  key = DENDRON_COMMANDS.BATCH_RENAME_NOTE.key;
  private extension: IDendronExtension;

  constructor(ext: IDendronExtension) {
    super();
    this.extension = ext;
  }

  async sanityCheck() {
    if (_.isUndefined(VSCodeUtils.getActiveTextEditor())) {
      return "No document open";
    }
    return;
  }

  async gatherInputs(): Promise<CommandOpts | undefined> {
    const editor = VSCodeUtils.getActiveTextEditor();
    if (!editor) {
      return;
    }

    // Get current note's fname
    const note = await WSUtilsV2.instance().getNoteFromDocument(
      editor.document
    );
    if (!note) {
      window.showErrorMessage("Could not determine current note.");
      return;
    }

    const oldPrefix = note.fname;

    // Show input box for new name
    const newPrefix = await VSCodeUtils.showInputBox({
      title: "Batch Rename Note",
      prompt: `Rename "${oldPrefix}" and all its children. Enter new name:`,
      value: oldPrefix,
      validateInput: (value: string) => {
        if (!value || value.trim() === "") {
          return "New name cannot be empty";
        }
        if (value === oldPrefix) {
          return "New name must be different from old name";
        }
        return undefined;
      },
    });

    if (_.isUndefined(newPrefix)) {
      return;
    }

    return {
      oldPrefix: oldPrefix,
      newPrefix: newPrefix.trim(),
    };
  }

  /**
   * Find all notes that are the target note or its children.
   * For prefix "A.B", this matches "A.B" and "A.B.*"
   */
  private async findAffectedNotes(
    oldPrefix: string
  ): Promise<DNodeProps[]> {
    const { engine } = ExtensionProvider.getDWorkspace();
    const allNotes = await engine.findNotes({ excludeStub: false });

    return allNotes.filter((note) => {
      if (DNodeUtils.isRoot(note)) return false;
      // Match exact fname or children (fname starts with oldPrefix + ".")
      return (
        note.fname === oldPrefix || note.fname.startsWith(oldPrefix + ".")
      );
    }).filter((note) => {
      // Filter out virtual stubs that don't exist on disk
      if (note.stub) {
        const notePath = NoteUtils.getFullPath({
          wsRoot: engine.wsRoot,
          note,
        });
        return fs.existsSync(notePath);
      }
      return true;
    });
  }

  /**
   * Generate rename operations from affected notes.
   * Replaces the old prefix with the new prefix in each fname.
   */
  private getRenameOperations(opts: {
    affectedNotes: DNodeProps[];
    oldPrefix: string;
    newPrefix: string;
    wsRoot: string;
  }): RenameOperation[] {
    const { affectedNotes, oldPrefix, newPrefix, wsRoot } = opts;

    return affectedNotes.map((note) => {
      const vault = note.vault;
      const vpath = vault2Path({ wsRoot, vault });
      const rootUri = Uri.file(vpath);

      // Replace the old prefix with new prefix
      let newFname: string;
      if (note.fname === oldPrefix) {
        newFname = newPrefix;
      } else {
        // note.fname starts with oldPrefix + "."
        newFname = newPrefix + note.fname.substring(oldPrefix.length);
      }

      return {
        vault,
        oldUri: VSCodeUtils.joinPath(rootUri, note.fname + ".md"),
        newUri: VSCodeUtils.joinPath(rootUri, newFname + ".md"),
      };
    });
  }

  /**
   * Check if any of the target files already exist (would cause overwrite).
   */
  private async hasExistingFiles(operations: RenameOperation[]): Promise<boolean> {
    const conflicts = operations.filter((op) =>
      fs.pathExistsSync(op.newUri.fsPath)
    );

    if (!_.isEmpty(conflicts)) {
      const content = [
        "# Error - Batch Rename would overwrite files",
        "",
        "### The following files would be overwritten:",
        "",
        "||||\n|-|-|-|",
      ]
        .concat(
          conflicts.map(
            ({ oldUri, newUri }) =>
              `| ${path.basename(oldUri.fsPath)} |-->| ${path.basename(
                newUri.fsPath
              )} |`
          )
        )
        .join("\n");

      const panel = window.createWebviewPanel(
        "batchRenamePreview",
        "Batch Rename Error",
        ViewColumn.One,
        {}
      );
      panel.webview.html = md.render(content);
      window.showErrorMessage(
        "Batch rename would overwrite existing files. Operation cancelled."
      );
      return true;
    }
    return false;
  }

  /**
   * Show a preview of all rename operations to the user.
   */
  private showPreview(operations: RenameOperation[]) {
    let content = [
      "# Batch Rename Preview",
      "",
      `## ${operations.length} file(s) will be renamed`,
      "",
    ];

    content = content.concat(
      _.map(
        _.groupBy(operations, "vault.fsPath"),
        (ops: RenameOperation[], k: string) => {
          const out = [`**Vault:** ${k}`].concat("\n||||\n|-|-|-|");
          return out
            .concat(
              ops.map(
                ({ oldUri, newUri }) =>
                  `| ${path.basename(oldUri.fsPath)} |-->| ${path.basename(
                    newUri.fsPath
                  )} |`
              )
            )
            .join("\n");
        }
      )
    );

    const panel = window.createWebviewPanel(
      "batchRenamePreview",
      "Batch Rename Preview",
      { viewColumn: ViewColumn.One, preserveFocus: true },
      {}
    );
    panel.webview.html = md.render(content.join("\n"));
  }

  /**
   * Run all rename operations sequentially.
   */
  private async runOperations(
    operations: RenameOperation[]
  ): Promise<RenameNoteOutputV2a> {
    const ctx = "BatchRenameNote:runOperations";
    const renameCmd = new RenameNoteV2aCommand();

    const out = await _.reduce<
      RenameOperation,
      Promise<RenameNoteOutputV2a>
    >(
      operations,
      async (respPromise, op) => {
        const acc = await respPromise;
        this.L.info({
          ctx,
          orig: op.oldUri.fsPath,
          replace: op.newUri.fsPath,
        });
        const resp = await renameCmd.execute({
          files: [op],
          silent: true,
          closeCurrentFile: false,
          openNewFile: false,
          noModifyWatcher: true,
        });
        acc.changed = resp.changed.concat(acc.changed);
        return acc;
      },
      Promise.resolve({ changed: [] })
    );

    return out;
  }

  async execute(opts: CommandOpts): Promise<CommandOutput> {
    const ctx = "BatchRenameNote:execute";
    const { oldPrefix, newPrefix, noConfirm } = opts;
    this.L.info({ ctx, opts, msg: "enter" });

    const ext = ExtensionProvider.getExtension();
    const { engine } = ExtensionProvider.getDWorkspace();

    // 1. Find all affected notes
    const affectedNotes = await this.findAffectedNotes(oldPrefix);

    if (affectedNotes.length === 0) {
      window.showWarningMessage(`No notes found with prefix "${oldPrefix}".`);
      return { changed: [], operations: [] };
    }

    // 2. Generate rename operations
    const operations = this.getRenameOperations({
      affectedNotes,
      oldPrefix,
      newPrefix,
      wsRoot: engine.wsRoot,
    });

    // 3. Check for conflicts
    if (await this.hasExistingFiles(operations)) {
      return { changed: [], operations: [] };
    }

    // 4. Show preview
    this.showPreview(operations);

    // 5. Ask for confirmation
    if (!noConfirm) {
      const options = ["Proceed", "Cancel"];
      const resp = await VSCodeUtils.showQuickPick(options, {
        title: `Batch rename ${operations.length} note(s)?`,
        placeHolder: "Proceed",
        ignoreFocusOut: true,
      });
      if (resp !== "Proceed") {
        window.showInformationMessage("Batch rename cancelled.");
        return { changed: [], operations: [] };
      }
    }

    // 6. Pause file watcher
    if (ext.fileWatcher) {
      ext.fileWatcher.pause = true;
    }

    // 7. Execute all rename operations with progress
    const out = await window.withProgress(
      {
        location: ProgressLocation.Notification,
        title: "Batch renaming notes...",
        cancellable: false,
      },
      async () => {
        return this.runOperations(operations);
      }
    );

    // 8. Resume file watcher
    if (ext.fileWatcher) {
      setTimeout(() => {
        if (ext.fileWatcher) {
          ext.fileWatcher.pause = false;
        }
        this.L.info({ ctx, state: "exit:pause_filewatcher" });
      }, 3000);
    }

    return { ...out, operations };
  }

  async showResponse(res: CommandOutput) {
    if (_.isUndefined(res) || res.operations.length === 0) {
      return;
    }
    const { changed, operations } = res;
    window.showInformationMessage(
      `Batch rename complete: ${operations.length} note(s) renamed, ${
        _.uniqBy(changed, (ent) => ent.note.fname).length
      } file(s) updated.`
    );
  }

  addAnalyticsPayload(_opts: CommandOpts, out: CommandOutput) {
    const noteChangeEntryCounts =
      out !== undefined
        ? { ...extractNoteChangeEntryCounts(out.changed) }
        : {
            createdCount: 0,
            updatedCount: 0,
            deletedCount: 0,
          };
    return noteChangeEntryCounts;
  }
}
