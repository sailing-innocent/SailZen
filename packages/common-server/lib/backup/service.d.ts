import { Disposable, DLogger, RespV3 } from "@saili/common-all";
import { IBackupService } from "./backupServiceInterface";
export type BackupServiceOpts = {
    wsRoot: string;
};
/**
 * Predefined keys to be used for backups
 * Loop over values when extracting keys
 * ^6ao9nojre6ai
 */
export declare enum BackupKeyEnum {
    config = "config"
}
export declare const BACKUP_DIR_NAME = ".backup";
export declare class BackupService implements Disposable, IBackupService {
    wsRoot: string;
    logger: DLogger;
    private loggerDispose;
    constructor({ wsRoot }: BackupServiceOpts);
    /**
     * dispose backup service.
     */
    dispose(): void;
    /**
     * getter for backup root path.
     * returns regardless of the existence of the directory.
     */
    get backupRoot(): string;
    /**
     * Makes sure the backup root ({@link backupRoot})
     * and directory for each defined key ({@link BackupKeyEnum}) exists.
     * Creates one otherwise.
     * Adds an entry to gitignore of workspace root if it isn't added already.
     */
    ensureBackupDir(): Promise<void>;
    /**
     * Given some options and a file name, generate a new file name to use for the backup.
     *
     * The format would be:
     *
     * `{file name without extension}.{yyyy.MM.dd.HHmmssS, if enabled}.{infix, if enabled}.{extension}`
     *
     * e.g.) Given `sail.yml`, timestamp, and infix `migrate-config`,
     * the resulting backup file name is `sail.2022.03.14.3239848.migrate-config.yml`
     *
     * Note that with `timestamp: false` and no infix, this will return the same inputted filename.
     *
     * @param opts.fileName file name to generate backup name for. Assumes existence of extension.
     * @param opts.timestamp flag to enable adding timestamp to name.
     * @param opts.infix optional custom infix to append right before the extension.
     * @returns generated backup file name.
     */
    generateBackupFileName(opts: {
        fileName: string;
        timestamp?: boolean;
        infix?: string;
    }): string;
    /**
     * Back up {@link opts.pathToBackup} to directory `{@link backupRoot}/{@link opts.key}`
     * with optional {@link opts.timestamp} and {@link opts.infix} in its name.
     * Or use {@link opts.nameOverride} as the backup name.
     *
     * See {@link generateBackupFileName} to see how backup names are generated.
     *
     * @param opts.key key to use for backup.
     * @param opts.pathToBackup path of file to back up.
     * @param opts.timestamp flag to enable timestamp in backup file name.
     * @param opts.infix optional custom infix to append right before the extension.
     * @param opts.nameOverride if given, it will be used instead of calling {@link generateBackupFileName}.
     * @returns A promise of response containing either the path of the backup or a SailError
     * ^b0jdi7ncbflr
     */
    backup(opts: {
        key: BackupKeyEnum;
        pathToBackup: string;
        timestamp?: boolean;
        infix?: string;
        nameOverride?: string;
    }): Promise<RespV3<string>>;
    /**
     * Given a {@link opts.key}, return all backups created with this key.
     * @param opts.key backup key to use. One of {@link BackupKeyEnum} as string.
     * @returns list of backups with given key.
     */
    getBackupsWithKey(opts: {
        key: string;
    }): string[];
    /**
     * @returns all backups grouped by backup key defined by {@link BackupKeyEnum}.
     */
    getAllBackups(): {
        key: string;
        backups: string[];
    }[];
}
