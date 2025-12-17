import { DStore } from "@saili/common-all";
import { DLogger } from "@saili/common-server";

export class ParserBase {
  constructor(public opts: { store: DStore; logger: DLogger }) {}

  get logger() {
    return this.opts.logger;
  }
}
