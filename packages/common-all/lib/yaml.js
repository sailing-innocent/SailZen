import YAML from "js-yaml";
import { fromThrowable } from "neverthrow";
import { ERROR_SEVERITY } from "./constants";
import { SailError } from "./error";
const load = fromThrowable(YAML.load, (error) => {
    return new SailError({
        message: error instanceof YAML.YAMLException
            ? `${error.name}: ${error.message}`
            : `YAMLException`,
        severity: ERROR_SEVERITY.FATAL,
        ...(error instanceof Error && { innerError: error }),
    });
});
const dump = fromThrowable(YAML.dump, (error) => {
    return new SailError({
        message: error instanceof YAML.YAMLException
            ? `${error.name}: ${error.message}`
            : `YAMLException`,
        severity: ERROR_SEVERITY.FATAL,
        ...(error instanceof Error && { innerError: error }),
    });
});
export const fromStr = (str, overwriteDuplicate) => {
    return load(str, {
        schema: YAML.JSON_SCHEMA,
        json: overwriteDuplicate ?? false,
    });
};
export const toStr = (data) => {
    return dump(data, { indent: 4, schema: YAML.JSON_SCHEMA });
};
//# sourceMappingURL=yaml.js.map