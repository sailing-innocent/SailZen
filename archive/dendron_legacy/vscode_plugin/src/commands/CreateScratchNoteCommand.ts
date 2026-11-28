import { Logger } from "../logger";
import { SAIL_COMMANDS } from "../constants";
import { BasicCommand } from "./base";
import { LookupControllerCreateOpts } from "../components/lookup/LookupController";
import { ILookupController } from "../components/lookup/LookupControllerInterface";
import {
  CopyNoteLinkBtn,
  HorizontalSplitBtn,
  ScratchBtn,
  Selection2LinkBtn,
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

export { CommandOpts as LookupScratchNoteOpts };

export class CreateScratchNoteCommand extends BasicCommand<
  CommandOpts,
  CommandOutput
> {
  key = SAIL_COMMANDS.CREATE_SCRATCH.key;
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
        ScratchBtn.create({ pressed: true, canToggle: false }),
        Selection2LinkBtn.create(true),
        CopyNoteLinkBtn.create(false),
        HorizontalSplitBtn.create(false),
      ],
      title: "Create Scratch Note",
    };
    const controller = this.extension.lookupControllerFactory.create(opts);
    return controller;
  }

  async execute(opts: CommandOpts) {
    const ctx = "CreateScratchNote";
    Logger.info({ ctx, msg: "enter" });
    const lookupCmd = new NoteLookupCommand();
    lookupCmd.controller = this.createLookupController();
    await lookupCmd.run(opts);

  }
}

