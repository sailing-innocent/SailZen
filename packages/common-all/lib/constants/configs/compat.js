import _ from "lodash";
export const CONFIG_TO_MINIMUM_COMPAT_MAPPING = {
    1: { clientVersion: "0.0.0" },
    2: { clientVersion: "0.63.0" }, // config consolidation (commands namespace)
    3: { clientVersion: "0.65.0" }, // config consolidation (workspace namespace)
    4: { clientVersion: "0.70.0" }, // config consolidation (preview namespace)
    5: { clientVersion: "0.83.0", softMapping: true }, // config consolidation (publishing namespace): commented this out because adding this compat mapping would prevent users from keeping the v4 config and still use the cli for publishing. re-enable once we remove backward compatibility.
};
export class CompatUtils {
    static isSoftMapping(opts) {
        const softMapping = CONFIG_TO_MINIMUM_COMPAT_MAPPING[opts.configVersion].softMapping;
        return !_.isUndefined(softMapping) && softMapping;
    }
}
//# sourceMappingURL=compat.js.map