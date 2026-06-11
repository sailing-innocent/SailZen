import { DendronTreeViewKey } from "@saili/common-all";
import { MetadataService } from "@saili/engine-server";
import * as vscode from "vscode";
import {
  ProviderResult,
  TreeDataProvider,
  TreeItem,
  TreeItemCollapsibleState,
  Uri,
} from "vscode";

type DendronWorkspaceMenuItem = {
  fsPath: string;
};

/**
 * Data provider for the Recent Workspaces Tree View
 */
class RecentWorkspacesTreeDataProvider
  implements TreeDataProvider<DendronWorkspaceMenuItem>
{
  getTreeItem(element: DendronWorkspaceMenuItem): TreeItem {
    return {
      label: element.fsPath,
      collapsibleState: TreeItemCollapsibleState.None,
      tooltip: "Click to open the workspace",
      command: {
        title: "Open Workspace",
        command: "vscode.openFolder",
        arguments: [Uri.file(element.fsPath)],
      },
    };
  }

  getChildren(
    element?: DendronWorkspaceMenuItem
  ): ProviderResult<DendronWorkspaceMenuItem[]> {
    switch (element) {
      case undefined:
        return MetadataService.instance().RecentWorkspaces?.map(
          (workspacePath) => {
            return {
              fsPath: workspacePath,
            };
          }
        );
      default:
        return [];
    }
  }
}

/**
 * Creates a tree view for the 'Recent Workspaces' panel in the Dendron Custom
 * View Container
 * @returns
 */
export default function setupRecentWorkspacesTreeView(): vscode.TreeView<DendronWorkspaceMenuItem> {
  const treeView = vscode.window.createTreeView(
    DendronTreeViewKey.RECENT_WORKSPACES,
    {
      treeDataProvider: new RecentWorkspacesTreeDataProvider(),
    }
  );
  return treeView;
}
