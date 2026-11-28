import { DeleteSchemaResp, GetSchemaResp, QuerySchemaResp, SchemaDeleteRequest, SchemaQueryRequest, SchemaReadRequest, SchemaWriteRequest, WriteSchemaResp } from "@saili/common-all";
export declare class SchemaController {
    static singleton?: SchemaController;
    static instance(): SchemaController;
    get(req: SchemaReadRequest): Promise<GetSchemaResp>;
    create(req: SchemaWriteRequest): Promise<WriteSchemaResp>;
    delete({ ws, id, opts, }: SchemaDeleteRequest): Promise<DeleteSchemaResp>;
    query({ ws, qs }: SchemaQueryRequest): Promise<QuerySchemaResp>;
}
