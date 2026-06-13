import { DConfig } from "@saili/common-server";
import { Uri } from "vscode";
import { DENDRON_COMMANDS } from "../constants";
import { ISailExtension } from "../sailExtensionInterface";
import { VSCodeUtils } from "../vsCodeUtils";
import { BasicCommand } from "./base";

type CommandOpts = {};

type CommandOutput = void;

export class ConfigureCommand extends BasicCommand<CommandOpts, CommandOutput> {
  key = DENDRON_COMMANDS.CONFIGURE_RAW.key;
  public static requireActiveWorkspace: boolean = true;
  private _ext: ISailExtension;

  constructor(extension: ISailExtension) {
    super();
    this._ext = extension;
  }

  async gatherInputs(): Promise<any> {
    return {};
  }
  async execute() {
    const sailRoot = this._ext.getDWorkspace().wsRoot;
    const configPath = DConfig.configPath(sailRoot);
    const uri = Uri.file(configPath);
    await VSCodeUtils.openFileInEditor(uri);
    return;
  }
}
