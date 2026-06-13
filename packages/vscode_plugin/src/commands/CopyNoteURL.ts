import { ConfigUtils } from "@saili/common-all";
import { WorkspaceUtils } from "@saili/engine-server";
import _ from "lodash";
import { Selection, window } from "vscode";
import { CONFIG, SAIL_COMMANDS } from "../constants";
import { ISailExtension } from "../sailExtensionInterface";
import { clipboard } from "../utils";
import { EditorUtils } from "../utils/EditorUtils";
import { VSCodeUtils } from "../vsCodeUtils";
import { SailExtension } from "../workspace";
import { WSUtils } from "../WSUtils";
import { BasicCommand } from "./base";

type CommandOpts = {};

type CommandOutput = string | undefined;

export class CopyNoteURLCommand extends BasicCommand<
  CommandOpts,
  CommandOutput
> {
  key = SAIL_COMMANDS.COPY_NOTE_URL.key;
  private extension: ISailExtension;

  constructor(ext: ISailExtension) {
    super();
    this.extension = ext;
  }

  async gatherInputs(): Promise<any> {
    return {};
  }

  async showFeedback(link: string) {
    window.showInformationMessage(`${link} copied`);
  }

  isHeader(text: string, selection: Selection) {
    return text.startsWith("#") && selection.start.line === selection.end.line;
  }

  async execute() {
    const { config } = this.extension.getDWorkspace();
    const publishingConfig = ConfigUtils.getPublishing(config);
    const urlRoot =
      publishingConfig.siteUrl ||
      SailExtension.configuration().get<string>(
        CONFIG.COPY_NOTE_URL_ROOT.key
      );
    const maybeTextEditor = VSCodeUtils.getActiveTextEditor();

    if (_.isUndefined(maybeTextEditor)) {
      window.showErrorMessage("no active document found");
      return;
    }
    const vault = WSUtils.instance().getVaultFromDocument(maybeTextEditor.document);

    const note = await WSUtils.instance().getNoteFromDocument(maybeTextEditor.document);
    if (_.isUndefined(note)) {
      window.showErrorMessage("You need to be in a note to use this command");
      return;
    }
    const { engine } = this.extension.getDWorkspace();

    // add the anchor if one is selected and exists
    const { selection, editor } = VSCodeUtils.getSelection();
    let anchor;
    if (selection) {
      anchor = EditorUtils.getAnchorAt({
        editor: editor!,
        position: selection.start,
        engine,
      });
    }

    const link = WorkspaceUtils.getNoteUrl({
      config,
      note,
      vault,
      urlRoot,
      anchor,
    });

    this.showFeedback(link);
    clipboard.writeText(link);
    return link;
  }
}

