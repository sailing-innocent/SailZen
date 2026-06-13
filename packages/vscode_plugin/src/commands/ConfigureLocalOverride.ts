import { DConfig, LocalConfigScope } from "@saili/common-server";
import fs from "fs-extra";
import { Uri } from "vscode";
import { SAIL_COMMANDS } from "../constants";
import { ISailExtension } from "../sailExtensionInterface";
import { MessageSeverity, VSCodeUtils } from "../vsCodeUtils";
import { BasicCommand } from "./base";

type CommandOpts = {
  configScope?: LocalConfigScope;
};

type CommandOutput = void;

export class ConfigureLocalOverride extends BasicCommand<
  CommandOpts,
  CommandOutput
> {
  key = SAIL_COMMANDS.CONFIGURE_LOCAL_OVERRIDE.key;
  public static requireActiveWorkspace: boolean = true;
  _ext: ISailExtension;

  constructor(extension: ISailExtension) {
    super();
    this._ext = extension;
  }

  async execute(opts?: CommandOpts) {
    /* In the test environemnt, configScope is passed as option for this command */
    const configScope = opts?.configScope || (await getConfigScope());

    if (configScope === undefined) {
      VSCodeUtils.showMessage(
        MessageSeverity.ERROR,
        "Configuration scope needs to be selected to open sailrc.yml file",
        {}
      );
      return;
    }

    const sailRoot = this._ext.getDWorkspace().wsRoot;
    const configPath = DConfig.configOverridePath(sailRoot, configScope);

    /* If the config file doesn't exist, create one */
    await fs.ensureFile(configPath);

    const uri = Uri.file(configPath);
    // What happens if the file doesn't exist
    await VSCodeUtils.openFileInEditor(uri);

    return;
  }
}

const getConfigScope = async (): Promise<LocalConfigScope | undefined> => {
  const options = [
    {
      label: LocalConfigScope.WORKSPACE,
      detail: "Configure sailrc.yml for current workspace",
    },
    {
      label: LocalConfigScope.GLOBAL,
      detail: "Configure sailrc.yml for all sail workspaces",
    },
  ];

  const scope = await VSCodeUtils.showQuickPick(options, {
    title: "Select configuration scope",
    placeHolder: "vault",
    ignoreFocusOut: true,
  });

  return scope ? (scope.label as LocalConfigScope) : undefined;
};
