import { SailError, } from "@saili/common-all";
import { DConfig } from "@saili/common-server";
import { MemoryStore } from "../store/memoryStore";
import { getWSEngine } from "../utils";
export class ConfigController {
    static singleton;
    static instance() {
        if (!ConfigController.singleton) {
            ConfigController.singleton = new ConfigController();
        }
        return ConfigController.singleton;
    }
    async get({ ws }) {
        const engine = ws
            ? await getWSEngine({ ws })
            : MemoryStore.instance().getEngine();
        try {
            return { data: DConfig.readConfigSync(engine.wsRoot) };
        }
        catch (err) {
            return {
                error: new SailError({ message: JSON.stringify(err) }),
            };
        }
    }
}
//# sourceMappingURL=config.js.map