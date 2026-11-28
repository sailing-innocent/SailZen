import { SailError } from "@saili/common-all";
import _ from "lodash";
const STORE = {};
export class MemoryStore {
    static _instance;
    static instance(force) {
        if (!MemoryStore._instance || force) {
            MemoryStore._instance = new MemoryStore();
        }
        return MemoryStore._instance;
    }
    static store = () => {
        return STORE;
    };
    async put(key, value) {
        STORE[key] = value;
    }
    getEngine() {
        const out = _.values(STORE)[0];
        if (!out) {
            throw new SailError({ message: "STORE is empty" });
        }
        return out;
    }
    async get(key) {
        return STORE[key];
    }
    async list(prefix) {
        const keys = _.filter(_.keys(STORE), (ent) => ent.startsWith(prefix));
        return _.pick(STORE, keys);
    }
}
//# sourceMappingURL=memoryStore.js.map