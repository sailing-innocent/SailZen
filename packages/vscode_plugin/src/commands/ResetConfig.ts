import _ from "lodash";
import { window } from "vscode";
import { DENDRON_COMMANDS } from "../constants";
import { ExtensionProvider } from "../ExtensionProvider";
import { GLOBAL_STATE, WORKSPACE_STATE } from "../constants";
import { BasicCommand } from "./base";

type ConfigScope = "local" | "global" | "all";
type CommandOpts = {
  scope: ConfigScope;
};

type CommandOutput = void;

type CommandInput = {
  scope: ConfigScope;
};

const valid = ["local", "global", "all"];

export class ResetConfigCommand extends BasicCommand<
  CommandOpts,
  CommandOutput
> {
  key = DENDRON_COMMANDS.RESET_CONFIG.key;
  async gatherInputs(): Promise<CommandInput | undefined> {
    const scope = await window.showInputBox({
      prompt: "Select scope",
      ignoreFocusOut: true,
      validateInput: (input: string) => {
        if (!_.includes(valid, input)) {
          return `input must be one of ${valid.join(", ")}`;
        }
        return undefined;
      },
      value: "all",
    });
    if (!scope) {
      return;
    }
    return { scope } as CommandInput;
  }

  async execute(opts: CommandOpts) {
    const scope = opts.scope;
    const { globalState, workspaceState } = ExtensionProvider.getExtension().context;
    if (scope === "all" || scope === "global") {
      _.values(GLOBAL_STATE).forEach((k) => {
        globalState.update(k, undefined);
      });
    }
    if (scope === "all" || scope === "local") {
      _.values(WORKSPACE_STATE).forEach((k) => {
        workspaceState.update(k, undefined);
      });
    }
    window.showInformationMessage(`reset config`);
    return;
  }
}
