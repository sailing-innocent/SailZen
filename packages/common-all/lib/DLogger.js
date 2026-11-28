/**
 * A simple DLogger implementation that just logs to console. This logger works
 * on all platforms.
 */
export class ConsoleLogger {
    name;
    level;
    debug(msg) {
        console.log(`DEBUG: ${msg}`);
    }
    info(msg) {
        console.log(`INFO: ${msg}`);
    }
    error(msg) {
        console.log(`ERROR: ${msg}`);
    }
}
//# sourceMappingURL=DLogger.js.map