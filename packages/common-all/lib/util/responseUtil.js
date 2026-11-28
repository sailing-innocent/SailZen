import _ from "lodash";
/** Utility for {@link RespV2} */
export class ResponseUtil {
    /** true when response has an error; false otherwise. */
    static hasError(resp) {
        return !_.isNull(resp.error);
    }
    static createHappyResponse(input) {
        return {
            error: null,
            data: input.data,
        };
    }
    static createUnhappyResponse(input) {
        return {
            error: input.error,
            data: undefined,
        };
    }
}
//# sourceMappingURL=responseUtil.js.map