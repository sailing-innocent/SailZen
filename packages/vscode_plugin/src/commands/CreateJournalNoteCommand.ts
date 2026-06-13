import { Logger } from "../logger";
import { DENDRON_COMMANDS } from "../constants";
import { BasicCommand } from "./base";
import { LookupControllerCreateOpts } from "../components/lookup/LookupController";
import { ILookupController } from "../components/lookup/LookupControllerInterface";
import {
  CopyNoteLinkBtn,
  HorizontalSplitBtn,
  JournalBtn,
} from "../components/lookup/buttons";
import {
  CommandRunOpts as NoteLookupRunOpts,
  NoteLookupCommand,
} from "./NoteLookupCommand";
import { ISailExtension } from "../sailExtensionInterface";
import { ConfigUtils } from "@saili/common-all";
import { VaultSelectionModeConfigUtils } from "../components/lookup/vaultSelectionModeConfigUtils";

type CommandOpts = NoteLookupRunOpts;
type CommandOutput = void;

export { CommandOpts as CreateJournalNoteOpts };

export class CreateJournalNoteCommand extends BasicCommand<
  CommandOpts,
  CommandOutput
> {
  key = DENDRON_COMMANDS.CREATE_JOURNAL.key;
  private extension: ISailExtension;

  constructor(ext: ISailExtension) {
    super();
    this.extension = ext;
  }

  createLookupController(): ILookupController {
    const commandConfig = ConfigUtils.getCommands(
      this.extension.getDWorkspace().config
    );
    const confirmVaultOnCreate = commandConfig.lookup.note.confirmVaultOnCreate;
    const vaultButtonPressed =
      VaultSelectionModeConfigUtils.shouldAlwaysPromptVaultSelection();
    const opts: LookupControllerCreateOpts = {
      nodeType: "note",
      disableVaultSelection: !confirmVaultOnCreate,
      vaultButtonPressed,
      extraButtons: [
        JournalBtn.create({ pressed: true, canToggle: false }),
        CopyNoteLinkBtn.create(false),
        HorizontalSplitBtn.create(false),
      ],
      title: "Create Journal Note",
    };
    const controller = this.extension.lookupControllerFactory.create(opts);
    return controller;
  }

  async execute(opts: CommandOpts) {
    const ctx = "CreateJournalNote";
    Logger.info({ ctx, msg: "enter" });
    const lookupCmd = new NoteLookupCommand();
    lookupCmd.controller = this.createLookupController();
    await lookupCmd.run(opts);
  }
}

