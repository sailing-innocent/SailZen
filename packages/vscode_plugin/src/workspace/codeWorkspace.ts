import { DWorkspaceV2, WorkspaceType } from "@saili/common-all";
import { DendronBaseWorkspace } from "./baseWorkspace";

export class DendronCodeWorkspace
  extends DendronBaseWorkspace
  implements DWorkspaceV2
{
  public type = WorkspaceType.CODE;
}
