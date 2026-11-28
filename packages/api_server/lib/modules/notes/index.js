import { SailError, } from "@saili/common-all";
import { NodeJSUtils } from "@saili/common-server";
import { getLogger } from "../../core";
import { MemoryStore } from "../../store/memoryStore";
import { getWSEngine } from "../../utils";
export class NoteController {
    static singleton;
    static instance() {
        if (!NoteController.singleton) {
            NoteController.singleton = new NoteController();
        }
        return NoteController.singleton;
    }
    async render({ ws, ...opts }) {
        const engine = await getWSEngine({ ws });
        const data = await engine.renderNote(opts);
        return data;
    }
    async query({ ws, ...opts }) {
        const engine = ws
            ? await getWSEngine({ ws })
            : MemoryStore.instance().getEngine();
        return engine.queryNotes({ ...opts, originalQS: opts.qs });
    }
    async info() {
        const ctx = "NoteController:info";
        getLogger().info({ ctx, msg: "enter" });
        try {
            const version = NodeJSUtils.getVersionFromPkg();
            if (!version) {
                return {
                    error: SailError.createPlainError({
                        message: "Unable to read the Sail version",
                    }),
                };
            }
            return {
                data: {
                    version,
                },
            };
        }
        catch (err) {
            getLogger().error({ ctx, err });
            return {
                error: SailError.createPlainError({
                    payload: err,
                    message: "unknown error",
                }),
            };
        }
    }
    async rename({ ws, ...opts }) {
        const engine = await getWSEngine({ ws });
        const ctx = "NoteController:rename";
        try {
            getLogger().info({ ctx, msg: "enter" });
            const data = await engine.renameNote(opts);
            return data;
        }
        catch (err) {
            getLogger().error({ ctx, err });
            return {
                error: SailError.createPlainError({
                    payload: err,
                    message: "unknown error",
                }),
            };
        }
    }
}
//# sourceMappingURL=index.js.map