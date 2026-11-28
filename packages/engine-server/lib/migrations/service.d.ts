import { SailConfig, InstallStatus, WorkspaceSettings } from "@saili/common-all";
import { DLogger } from "@saili/common-server";
import { WorkspaceService } from "../workspace";
import { MigrationChangeSetStatus, Migrations } from "./types";
type ApplyMigrationRuleOpts = {
    currentVersion: string;
    previousVersion: string;
    sailConfig: SailConfig;
    wsConfig?: WorkspaceSettings;
    wsService: WorkspaceService;
    migrations?: Migrations[];
    runAll?: boolean;
    logger: DLogger;
};
export declare class MigrationService {
    static applyMigrationRules({ currentVersion, previousVersion, migrations, wsService, ...rest }: ApplyMigrationRuleOpts): Promise<MigrationChangeSetStatus[]>;
    /**
     * Creates a list of changes that will need to be applied
     */
    static collectMigrationChanges({ previousVersion, migration, wsService, logger, ...rest }: {
        migration: Migrations;
    } & ApplyMigrationRuleOpts): Promise<MigrationChangeSetStatus[]>;
    /**
     * Should we attempt to migrate workspace settings
     * @returns
     */
    static shouldRunMigration({ force, workspaceInstallStatus, }: {
        force?: boolean;
        workspaceInstallStatus: InstallStatus;
    }): boolean | undefined;
}
export {};
