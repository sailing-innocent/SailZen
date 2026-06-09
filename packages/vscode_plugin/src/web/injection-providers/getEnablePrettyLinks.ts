import { ConfigUtils } from "@saili/common-all";
import { Uri } from "vscode";
import { getWorkspaceConfig } from "./getWorkspaceConfig";

/**
 * Get the enablePrettyLinks from publishing config
 * @param wsRoot
 * @returns value of enablePrettyLinks from publishing config
 *
 * NOTE: 上游 ConfigUtils.getEnablePrettlyLinks 仍有拼写错误，留待后续修复
 */
export async function getEnablePrettyLinks(
  wsRoot: Uri
): Promise<boolean | undefined> {
  const config = await getWorkspaceConfig(wsRoot);
  return ConfigUtils.getEnablePrettlyLinks(config) || true;
}
