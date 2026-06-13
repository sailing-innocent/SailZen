import { SailConfigEntryCollection } from "../../types/configs/base";
import { SailConfig } from "../../types/configs/sailConfig";
import { GLOBAL } from "./global";
import { COMMANDS } from "./commands";
import { WORKSPACE } from "./workspace";
import { PREVIEW } from "./preview";
import { PUBLISHING } from "./publishing";
import { DEV } from "./dev";

export const DENDRON_CONFIG: SailConfigEntryCollection<SailConfig> = {
  version: {
    label: "Version",
    desc: "Version number for configuration. Automatically set up by plugin during migration.",
  },
  global: GLOBAL,
  commands: COMMANDS,
  workspace: WORKSPACE,
  preview: PREVIEW,
  publishing: PUBLISHING,
  dev: DEV,
};
