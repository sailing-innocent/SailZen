import _ from "lodash";
export class AssertionError extends Error {
}
export function assertExists(val, msg) {
    if (_.isNull(val) || _.isUndefined(val)) {
        throw new AssertionError(msg);
    }
    // @ts-ignore
    return val;
}
export function assert(statement, msg) {
    if (!statement) {
        throw new AssertionError(msg);
    }
    else {
        return true;
    }
}
//# sourceMappingURL=assert.js.map