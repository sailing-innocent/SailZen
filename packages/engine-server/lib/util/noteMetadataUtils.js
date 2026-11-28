import { SailError, ErrorFactory, isNumeric, minimatch, } from "@saili/common-all";
import _ from "lodash";
import { DateTime } from "luxon";
import { LinkUtils } from "@saili/unified";
var NullOrUndefined;
(function (NullOrUndefined) {
    NullOrUndefined[NullOrUndefined["UNDEFINED"] = 0] = "UNDEFINED";
    NullOrUndefined[NullOrUndefined["NULL"] = 1] = "NULL";
    NullOrUndefined[NullOrUndefined["NO_UNDEFINED_OR_NULL"] = 2] = "NO_UNDEFINED_OR_NULL";
})(NullOrUndefined || (NullOrUndefined = {}));
export class NoteMetadataUtils {
    /**
     * Return list of strings from links
     * @param links
     */
    static cleanTags(links) {
        return links.map((l) => {
            return l.value.replace(/^tags./, "");
        });
    }
    static checkIfAllowNullOrUndefined(val, { required, strictNullChecks }) {
        if (_.isUndefined(val) && !required) {
            return NullOrUndefined.UNDEFINED;
        }
        if (_.isNull(val) && !strictNullChecks) {
            return NullOrUndefined.NULL;
        }
        return NullOrUndefined.NO_UNDEFINED_OR_NULL;
    }
    static checkAndReturnUndefinedOrError(val, props) {
        if (NoteMetadataUtils.checkIfAllowNullOrUndefined(val, props) !==
            NullOrUndefined.NO_UNDEFINED_OR_NULL) {
            return { data: undefined };
        }
        return {
            error: ErrorFactory.createInvalidStateError({
                message: `${val} is wrong type`,
            }),
        };
    }
    static checkIfSkipOnEmpty(key, val, props) {
        const { skipOnEmpty = true } = props;
        if (_.isEmpty(val) && skipOnEmpty) {
            return { data: undefined };
        }
        if (_.isEmpty(val) && !skipOnEmpty) {
            return {
                error: ErrorFactory.createInvalidStateError({
                    message: `The value for ${key} is found empty. Please provide a valid value or enable skipOnEmpty in the srcFieldMapping.`,
                }),
            };
        }
        return { data: val };
    }
    /**
     * Extract string metadata from note
     * @returns
     */
    static extractString({ note, key, ...props }) {
        const val = _.get(note, key);
        if (_.isString(val)) {
            return { data: val };
        }
        return NoteMetadataUtils.checkAndReturnUndefinedOrError(val, props);
    }
    static extractNumber({ note, key, ...props }) {
        const val = _.get(note, key);
        if (_.isNumber(val)) {
            return { data: val };
        }
        if (isNumeric(val)) {
            return { data: parseFloat(val) };
        }
        return NoteMetadataUtils.checkAndReturnUndefinedOrError(val, props);
    }
    static extractBoolean({ note, key, ...props }) {
        const val = _.get(note, key);
        if (_.isBoolean(val)) {
            return { data: val };
        }
        return NoteMetadataUtils.checkAndReturnUndefinedOrError(val, props);
    }
    static extractDate({ note, key, ...props }) {
        // TODO: we should validate
        const val = _.get(note, key);
        if (_.isNumber(val)) {
            return {
                data: DateTime.fromMillis(val).toLocaleString(DateTime.DATETIME_FULL),
            };
        }
        return NoteMetadataUtils.checkIfSkipOnEmpty(key, val, props);
    }
    /**
     * If field is not found, return empty array
     */
    static extractArray({ note, key, }) {
        return _.get(note, key, []);
    }
    /**
     * Get all links from a note
     */
    static extractLinks({ note, filters }) {
        let links = note.links;
        filters.map((pattern) => {
            links = links.filter((t) => minimatch(t.value, pattern));
        });
        return links;
    }
    /**
     * Get hashtags from note
     */
    static extractTags({ note, filters }) {
        let links = LinkUtils.findHashTags({ links: note.links });
        filters.map((pattern) => {
            links = links.filter((t) => minimatch(t.value, pattern));
        });
        return links;
    }
    static extractSingleTag({ note, filters, }) {
        const tags = this.extractTags({ note, filters });
        if (tags.length > 1) {
            const error = new SailError({
                message: `singleTag field has multiple values. note: ${note.fname}, tags: ${tags.map((ent) => ent.alias).join(", ")}`,
            });
            return { error };
        }
        if (tags.length === 0) {
            return { data: undefined };
        }
        return { data: tags[0] };
    }
}
//# sourceMappingURL=noteMetadataUtils.js.map