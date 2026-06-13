import { SailError, ConfigUtils } from "@saili/common-all";
import _ from "lodash";
import { Migrations } from "./types";
import { MigrationUtils, PATH_MAP } from "./utils";
import { DEPRECATED_PATHS } from ".";
import { DConfig } from "@saili/common-server";

export const CONFIG_MIGRATIONS: Migrations = {
  version: "0.83.0",
  changes: [
    {
      /**
       * This is the migration that was done to clean up all legacy config namespaces.
       */
      name: "migrate config",
      func: async ({ sailConfig, wsConfig, wsService }) => {
        try {
          await DConfig.createBackup(wsService.wsRoot, "migrate-configs");
        } catch (error) {
          return {
            data: {
              sailConfig,
              wsConfig,
            },
            error: new SailError({
              message:
                "Backup failed during config migration. Exiting without migration.",
            }),
          };
        }

        const defaultV5Config = ConfigUtils.genDefaultConfig();
        const rawSailConfig = DConfig.getRaw(wsService.wsRoot);

        // remove all null properties
        const cleanSailConfig = MigrationUtils.deepCleanObjBy(
          rawSailConfig,
          _.isNull
        );

        if (_.isUndefined(cleanSailConfig.commands)) {
          cleanSailConfig.commands = {};
        }

        if (_.isUndefined(cleanSailConfig.workspace)) {
          cleanSailConfig.workspace = {};
        }

        if (_.isUndefined(cleanSailConfig.preview)) {
          cleanSailConfig.preview = {};
        }

        if (_.isUndefined(cleanSailConfig.publishing)) {
          cleanSailConfig.publishing = {};
        }

        // legacy paths to remove from config;
        const legacyPaths: string[] = [];
        // migrate each path mapped in current config version
        PATH_MAP.forEach((value, key) => {
          const { target: legacyPath, preserve } = value;
          let iteratee = value.iteratee;
          let valueToFill;
          let alreadyFilled;

          if (iteratee !== "skip") {
            alreadyFilled = _.has(cleanSailConfig, key);
            const maybeLegacyConfig = _.get(cleanSailConfig, legacyPath);
            if (_.isUndefined(maybeLegacyConfig)) {
              // legacy property doesn't have a value.
              valueToFill = _.get(defaultV5Config, key);
            } else {
              // there is a legacy value.
              // check if this mapping needs special treatment.
              if (_.isUndefined(iteratee)) {
                // assume identity mapping.
                iteratee = _.identity;
              }
              valueToFill = iteratee(maybeLegacyConfig);
            }
          }

          if (!alreadyFilled && !_.isUndefined(valueToFill)) {
            // if the property isn't already filled, fill it with determined value.
            _.set(cleanSailConfig, key, valueToFill);
          }

          // these will later be used to delete.
          // only push if we aren't preserving target.
          if (!preserve) {
            legacyPaths.push(legacyPath);
          }
        });

        // set config version.
        _.set(cleanSailConfig, "version", 5);

        // add deprecated paths to legacyPaths
        // so they could be unset if they exist
        legacyPaths.push(...DEPRECATED_PATHS);

        // remove legacy property from config after migration.
        legacyPaths.forEach((legacyPath) => {
          _.unset(cleanSailConfig, legacyPath);
        });

        // recursively populate missing defaults
        const migratedConfig = _.defaultsDeep(
          cleanSailConfig,
          defaultV5Config
        );

        return { data: { sailConfig: migratedConfig, wsConfig } };
      },
    },
  ],
};

export const MIGRATION_ENTRIES = [CONFIG_MIGRATIONS];
