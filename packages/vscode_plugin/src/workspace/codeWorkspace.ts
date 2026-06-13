import { DWorkspaceV2, WorkspaceType } from "@saili/common-all";
import { SailBaseWorkspace } from "./baseWorkspace";

export class SailCodeWorkspace
  extends SailBaseWorkspace
  implements DWorkspaceV2 {
  public type = WorkspaceType.CODE;
}
