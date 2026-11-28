import axios from "axios";
import _ from "lodash";
import { SailError } from "./error";
export function createNoOpLogger() {
    const logMethod = (_msg) => { };
    return {
        level: "",
        debug: logMethod,
        info: logMethod,
        error: logMethod,
    };
}
/**
 * Convert an object to a query string using URLSearchParams.
 * Handles arrays by appending multiple values with the same key.
 * Replaces the deprecated querystring/qs library.
 */
export function stringifyQueryParams(params) {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value === null || value === undefined) {
            continue;
        }
        if (Array.isArray(value)) {
            // For arrays, append each value with the same key
            value.forEach((item) => {
                if (item !== null && item !== undefined) {
                    searchParams.append(key, String(item));
                }
            });
        }
        else if (typeof value === 'object') {
            // For nested objects, serialize as JSON string
            // This maintains compatibility with complex query structures
            searchParams.append(key, JSON.stringify(value));
        }
        else {
            searchParams.append(key, String(value));
        }
    }
    return searchParams.toString();
}
export class APIUtils {
    /** Generate a localhost url to this API.
     *
     * Warning! In VSCode, the generated URL won't work if the user has a remote
     * workspace. You'll need to use `vscode.env.asExternalUri` to make it remote.
     */
    static getLocalEndpoint(port) {
        return `http://localhost:${port}`;
    }
}
// === Base
class API {
    opts;
    constructor(opts) {
        opts = _.defaults(opts, {
            logger: createNoOpLogger(),
            statusHandlers: {},
            onAuth: async ({ headers }) => headers,
            onBuildHeaders: ({ headers }) => headers,
            onError: (_args) => {
                // console.log(args);
            },
        });
        if (!opts._request) {
            opts._request = axios.create({});
        }
        this.opts = opts;
    }
    _log(msg, lvl = "info") {
        this.opts.logger[lvl](msg);
    }
    _createPayload(data) {
        return {
            data,
        };
    }
    async _doRequest({ auth = false, qs = {}, path, body = {}, method = "get", json = true, }) {
        let headers = {};
        const { _request, onAuth, onBuildHeaders, endpoint, apiPath } = this.opts;
        if (auth) {
            headers = await onAuth({ headers });
        }
        headers = await onBuildHeaders({ headers });
        const requestParams = {
            url: [endpoint, apiPath, path].join("/"),
            qs,
            body,
            json,
            ...headers,
        };
        this._log({ ctx: "pre-request", requestParams }, "debug");
        const str = stringifyQueryParams(requestParams.qs);
        if (method === "get") {
            return _request.get(requestParams.url + `?${str}`, {
                headers,
            });
        }
        else {
            return _request.post(requestParams.url + `?${str}`, body, {
                headers,
            });
        }
    }
    async _makeRequest(args, payloadData) {
        const payload = this._createPayload(payloadData);
        try {
            const resp = await this._doRequest(args);
            payload.data = resp.data.data;
            payload.error = resp.data.error;
        }
        catch (err) {
            this._log(payload.error, "error");
            // Log errors from express:
            payload.error =
                err?.response?.data?.error || // Corresponds to an expected error that we intentionally log in our code
                    err?.response?.data || // Corresponds to an unexpected server error (HTTP 500) if a data payload was added
                    err; // Corresponds to an axios (HTTP request) thrown error
        }
        if (payload.error) {
            this._log(payload.error, "error");
        }
        return payload;
    }
    async _makeRequestRaw(args) {
        try {
            const resp = await this._doRequest(args);
            if (resp.data.error) {
                return new SailError({ ...resp.data.error });
            }
            return resp.data;
        }
        catch (err) {
            return new SailError({ ...err.response.data.error });
        }
    }
}
// === SailAPI
// eslint-disable-next-line camelcase
let _SailAPI_INSTANCE;
export class SailAPI extends API {
    static getOrCreate(opts) {
        if (!_.isUndefined(_SailAPI_INSTANCE)) {
            return this.instance();
        }
        return new SailAPI(opts);
    }
    static instance() {
        if (_.isUndefined(_SailAPI_INSTANCE)) {
            throw Error("no sail api");
        }
        // eslint-disable-next-line camelcase
        return _SailAPI_INSTANCE;
    }
    assetGet(req) {
        return this._makeRequestRaw({
            path: "assets/",
            method: "get",
            qs: req,
        });
    }
    assetGetTheme(req) {
        return this._makeRequestRaw({
            path: "assets/theme",
            method: "get",
            qs: req,
        });
    }
    configGet(req) {
        return this._makeRequest({
            path: "config/get",
            method: "get",
            qs: req,
        });
    }
    workspaceInit(req) {
        return this._makeRequest({
            path: "workspace/initialize",
            method: "post",
            body: {
                ...req,
            },
        });
    }
    workspaceInitStatus(req) {
        return this._makeRequest({
            path: "workspace/initStatus",
            method: "get",
            qs: req,
        });
    }
    workspaceSync(req) {
        return this._makeRequest({
            path: "workspace/sync",
            method: "post",
            body: req,
        });
    }
    engineBulkAdd(req) {
        return this._makeRequest({
            path: "note/bulkAdd",
            method: "post",
            body: req,
        });
    }
    engineDelete(req) {
        return this._makeRequest({
            path: "note/delete",
            method: "post",
            body: req,
        });
    }
    engineInfo() {
        return this._makeRequest({
            path: "note/info",
            method: "get",
        });
    }
    engineRenameNote(req) {
        return this._makeRequest({
            path: "note/rename",
            method: "post",
            body: req,
        });
    }
    engineWrite(req) {
        return this._makeRequest({
            path: "note/write",
            method: "post",
            body: req,
        });
    }
    noteGet(req) {
        return this._makeRequest({
            path: "note/get",
            method: "get",
            qs: req,
        });
    }
    noteGetMeta(req) {
        return this._makeRequest({
            path: "note/getMeta",
            method: "get",
            qs: req,
        });
    }
    noteBulkGet(req) {
        return this._makeRequest({
            path: "note/bulkGet",
            method: "get",
            qs: req,
        });
    }
    noteBulkGetMeta(req) {
        return this._makeRequest({
            path: "note/bulkGetMeta",
            method: "get",
            qs: req,
        });
    }
    noteFind(req) {
        return this._makeRequest({
            path: "note/find",
            method: "post",
            body: req,
        });
    }
    noteFindMeta(req) {
        return this._makeRequest({
            path: "note/findMeta",
            method: "post",
            body: req,
        });
    }
    noteQuery(req) {
        return this._makeRequest({
            path: "note/query",
            method: "get",
            qs: req,
        });
    }
    noteRender(req) {
        return this._makeRequest({
            path: "note/render",
            method: "post",
            body: req,
        });
    }
    getNoteBlocks(req) {
        return this._makeRequest({
            path: "note/blocks",
            method: "get",
            qs: req,
        });
    }
    getDecorations(req) {
        return this._makeRequest({
            path: "note/decorations",
            method: "post",
            body: req,
        });
    }
    schemaDelete(req) {
        return this._makeRequest({
            path: "schema/delete",
            method: "post",
            body: req,
        });
    }
    schemaRead(req) {
        return this._makeRequest({
            path: "schema/get",
            method: "get",
            qs: req,
        });
    }
    schemaQuery(req) {
        return this._makeRequest({
            path: "schema/query",
            method: "post",
            body: req,
        });
    }
    schemaWrite(req) {
        return this._makeRequest({
            path: "schema/write",
            method: "post",
            body: req,
        });
    }
}
export const SailApiV2 = SailAPI;
//# sourceMappingURL=api.js.map