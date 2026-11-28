import { getWSEngine } from "../../utils";
export class SchemaController {
    static singleton;
    static instance() {
        if (!SchemaController.singleton) {
            SchemaController.singleton = new SchemaController();
        }
        return SchemaController.singleton;
    }
    async get(req) {
        const { ws, id } = req;
        const engine = await getWSEngine({ ws: ws || "" });
        return engine.getSchema(id);
    }
    async create(req) {
        const { ws, schema, opts } = req;
        const engine = await getWSEngine({ ws });
        return engine.writeSchema(schema, opts);
    }
    async delete({ ws, id, opts, }) {
        const engine = await getWSEngine({ ws: ws || "" });
        return engine.deleteSchema(id, opts);
    }
    async query({ ws, qs }) {
        const engine = await getWSEngine({ ws: ws || "" });
        return engine.querySchema(qs);
    }
}
//# sourceMappingURL=index.js.map