import * as vscode from "vscode";
import { DENDRON_COMMANDS } from "../constants";
import { BasicCommand } from "./base";

export type InstrumentedWrapperCommandArgs = {
  /**
   * The underlying command to be wrapped
   */
  command: vscode.Command;
};

/**
 * This command is a simple wrapper around commands. This is intended to be used as a
 * wrapper around built-in VSCode commands that need to be invoked via a command
 * URI, such as within webviews or in TreeView items.
 */
export class InstrumentedWrapperCommand extends BasicCommand<
  InstrumentedWrapperCommandArgs,
  void
> {
  key = DENDRON_COMMANDS.INSTRUMENTED_WRAPPER_COMMAND.key;

  /**
   * Helper method to create a vscode.Command instance that utilizes this wrapper
   * @param args
   * @returns
   */
  public static createVSCodeCommand(
    args: InstrumentedWrapperCommandArgs
  ): vscode.Command {
    return {
      title: args.command.title,
      command: DENDRON_COMMANDS.INSTRUMENTED_WRAPPER_COMMAND.key,
      arguments: [args],
    };
  }

  async execute(opts: InstrumentedWrapperCommandArgs): Promise<void> {
    const args = opts.command.arguments ?? [];
    await vscode.commands.executeCommand(opts.command.command, ...args);

  }
}
