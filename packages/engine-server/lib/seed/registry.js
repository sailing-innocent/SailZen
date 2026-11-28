import { SEED_REGISTRY } from "@saili/common-all";
import { readYAML } from "@saili/common-server";
export class SeedRegistry {
    registry;
    static create(opts) {
        let registry = SEED_REGISTRY;
        if (opts?.registryFile) {
            registry = readYAML(opts.registryFile);
        }
        return new SeedRegistry(registry);
    }
    constructor(registry) {
        this.registry = registry;
    }
    info({ id }) {
        return this.registry[id];
    }
}
//# sourceMappingURL=registry.js.map