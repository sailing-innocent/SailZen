export class ParserBase {
    opts;
    constructor(opts) {
        this.opts = opts;
    }
    get logger() {
        return this.opts.logger;
    }
}
//# sourceMappingURL=parseBase.js.map