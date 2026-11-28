import { getStage, InstallStatus, ConfigUtils, } from "@saili/common-all";
import { createDisposableLogger } from "@saili/common-server";
import _ from "lodash";
import semver from "semver";
import { MIGRATION_ENTRIES } from "./migrations";
export class MigrationService {
    static async applyMigrationRules({ currentVersion, previousVersion, migrations, wsService, ...rest }) {
        const results = [];
        // run migrations from oldest to newest
        const migrationsToRun = _.reverse(_.takeWhile(migrations || MIGRATION_ENTRIES, (ent) => {
            const out = semver.lte(previousVersion, ent.version) &&
                semver.gte(currentVersion, ent.version);
            return out;
        }));
        const { logger, dispose } = createDisposableLogger("migration");
        logger.info({
            migrations: migrationsToRun.map((m) => [
                m.version,
                m.changes.map((c) => c.name),
            ]),
        });
        dispose();
        await _.reduce(migrationsToRun, async (prev, migration) => {
            await prev;
            const out = await this.collectMigrationChanges({
                currentVersion,
                previousVersion,
                migration,
                wsService,
                ...rest,
            });
            results.push(out);
            return out;
        }, Promise.resolve({}));
        const changes = _.flatten(results);
        if (!_.isEmpty(changes)) {
            const { data } = _.last(changes);
            // TODO: this should only be set if the migration is backwards incompatible with previous sail versions
            ConfigUtils.setWorkspaceProp(data.sailConfig, "sailVersion", currentVersion);
            await wsService.setConfig(data.sailConfig);
            // wsConfig is undefined for native workspaces
            if (data.wsConfig)
                wsService.setCodeWorkspaceSettingsSync(data.wsConfig);
        }
        return changes;
    }
    /**
     * Creates a list of changes that will need to be applied
     */
    static async collectMigrationChanges({ previousVersion, migration, wsService, logger, ...rest }) {
        const results = [];
        await _.reduce(migration.changes, async (prev, change) => {
            const { data } = await prev;
            logger.info({ ctx: "applyMigrationChange", name: change.name });
            const { sailConfig, wsConfig } = data;
            const out = await change.func({ sailConfig, wsConfig, wsService });
            const changeStatus = {
                data: {
                    changeName: change.name,
                    status: "ok",
                    version: migration.version,
                    ...out.data,
                },
            };
            results.push(changeStatus);
            return changeStatus;
        }, Promise.resolve({
            data: {
                changeName: "no-op",
                version: "",
                status: "ok",
                ...rest,
            },
        }));
        return results;
    }
    /**
     * Should we attempt to migrate workspace settings
     * @returns
     */
    static shouldRunMigration({ force, workspaceInstallStatus, }) {
        return ((workspaceInstallStatus === InstallStatus.UPGRADED || force) &&
            getStage() === "prod");
    }
}
//# sourceMappingURL=service.js.map