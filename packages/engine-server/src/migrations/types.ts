import {
  SailConfig,
  SailError,
  WorkspaceSettings,
} from "@saili/common-all";
import { WorkspaceService } from "../workspace";

export type MigrateFunction = (opts: {
  sailConfig: SailConfig;
  wsConfig?: WorkspaceSettings;
  wsService: WorkspaceService;
}) => Promise<{
  error?: SailError;
  data: {
    sailConfig: SailConfig;
    wsConfig?: WorkspaceSettings;
  };
}>;

export type MigrationChangeSet = {
  name: string;
  func: MigrateFunction;
};

export type Migrations = {
  version: string;
  changes: MigrationChangeSet[];
};

export type MigrationChangeSetStatus = {
  error?: SailError;
  data: {
    version: string;
    changeName: string;
    status: "ok" | "error";
    sailConfig: SailConfig;
    wsConfig?: WorkspaceSettings;
  };
};
