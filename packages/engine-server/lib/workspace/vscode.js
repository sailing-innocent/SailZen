import { CONSTANTS, } from "@saili/common-all";
import { assignJSONWithComment, readJSONWithComments, writeJSONWithCommentsSync, } from "@saili/common-server";
import fs from "fs-extra";
import _ from "lodash";
import path from "path";
export const _SETTINGS = {
    "sail.rootDir": {
        default: ".",
    },
    // "editor.minimap.enabled": {
    //   default: false,
    // },
    "files.autoSave": {
        default: "onFocusChange",
    },
    // --- images
    // eslint-disable-next-line no-template-curly-in-string
    "pasteImage.path": { default: "${currentFileDir}/assets/images" },
    // required for jekyll image build
    "pasteImage.prefix": { default: "/" },
    // -- md notes
    // prevent markdown-notes from mangling file names
    "markdown-preview-enhanced.enableWikiLinkSyntax": { default: true },
    "markdown-preview-enhanced.wikiLinkFileExtension": { default: ".md" },
    // --- snippets
    // add snippet completion
    "editor.snippetSuggestions": { default: "inline" },
    "editor.suggest.snippetsPreventQuickSuggestions": { default: false },
    "editor.suggest.showSnippets": { default: true },
    "editor.tabCompletion": { default: "on" },
};
const _EXTENSIONS = [
    { default: "sail.sail" },
    { default: "sail.sail-paste-image" },
    { default: "sail.sail-markdown-shortcuts" },
    // Autocomplete & warnings when editing `sail.yml`
    { default: "redhat.vscode-yaml" },
    { default: "sail.sail-markdown-links", action: "REMOVE" },
    { default: "sail.sail-markdown-notes", action: "REMOVE" },
    { default: "sail.sail-markdown-preview-enhanced", action: "REMOVE" },
    { default: "shd101wyy.markdown-preview-enhanced", action: "REMOVE" },
    { default: "kortina.vscode-markdown-notes", action: "REMOVE" },
    { default: "mushan.vscode-paste-image", action: "REMOVE" },
];
export class WorkspaceConfig {
    static genDefaults() {
        return {
            folders: [],
            settings: Settings.defaults(),
            extensions: Extensions.defaults(),
        };
    }
    static workspaceFile(wsRoot) {
        return path.join(wsRoot, CONSTANTS.SAIL_WS_NAME);
    }
    /**
     * Create sail.code-workspace file
     * @param wsRoot
     * @param vaults
     * @param opts
     * @returns
     */
    static write(wsRoot, vaults, opts) {
        const cleanOpts = _.defaults(opts, {
            vaults,
            overrides: {},
        });
        const defaultSettings = this.genDefaults();
        const jsonBody = _.merge(defaultSettings, {
            folders: cleanOpts.vaults
                ? cleanOpts.vaults.map((ent) => ({
                    path: ent.fsPath,
                    name: ent.name,
                }))
                : [],
        }, cleanOpts.overrides);
        return fs.writeJSONSync(WorkspaceConfig.workspaceFile(wsRoot), jsonBody, {
            spaces: 2,
        });
    }
}
export class Extensions {
    static EXTENSION_FILE_NAME = "extensions.json";
    static defaults() {
        const recommendations = Extensions.configEntries()
            .filter((ent) => {
            return _.isUndefined(ent.action) || ent?.action !== "REMOVE";
        })
            .map((ent) => ent.default);
        const unwantedRecommendations = Extensions.configEntries()
            .filter((ent) => {
            return ent?.action === "REMOVE";
        })
            .map((ent) => ent.default);
        return {
            recommendations,
            unwantedRecommendations,
        };
    }
    static configEntries() {
        return _EXTENSIONS;
    }
    static update(extensions) {
        const recommendations = new Set(extensions.recommendations);
        const unwantedRecommendations = new Set(extensions.unwantedRecommendations);
        const configEntries = Extensions.configEntries();
        configEntries.forEach((ent) => {
            if (ent?.action === "REMOVE") {
                recommendations.delete(ent.default);
                unwantedRecommendations.add(ent.default);
            }
            else {
                recommendations.add(ent.default);
                unwantedRecommendations.delete(ent.default);
            }
        });
        return {
            recommendations: Array.from(recommendations),
            unwantedRecommendations: Array.from(unwantedRecommendations),
        };
    }
}
export class Snippets {
    static filename = "sail.code-snippets";
    static defaults = {
        todo: {
            prefix: "to",
            scope: "markdown,yaml",
            body: "- [ ] ",
            description: "render todo box",
        },
        date: {
            prefix: "date",
            scope: "markdown,yaml",
            body: "$CURRENT_YEAR.$CURRENT_MONTH.$CURRENT_DATE",
            description: "today's date",
        },
        time: {
            prefix: "time",
            scope: "markdown,yaml",
            body: "$CURRENT_YEAR-$CURRENT_MONTH-$CURRENT_DATE $CURRENT_HOUR:$CURRENT_MINUTE",
            description: "time",
        },
    };
    static create = (dirPath) => {
        fs.ensureDirSync(dirPath);
        const snippetPath = path.join(dirPath, Snippets.filename);
        return fs.writeJSONSync(snippetPath, Snippets.defaults, { spaces: 4 });
    };
    static read = async (dirPath) => {
        const snippetPath = path.join(dirPath, Snippets.filename);
        if (!fs.existsSync(snippetPath)) {
            return false;
        }
        else {
            return readJSONWithComments(snippetPath);
        }
    };
    static async upgradeOrCreate(dirPath) {
        const out = await Snippets.read(dirPath);
        if (!out) {
            Snippets.create(dirPath);
            return Snippets.defaults;
        }
        else {
            const changed = {};
            const prefixKey = _.mapKeys(out, (ent) => ent.prefix);
            _.each(Snippets.defaults, (v, k) => {
                if (!_.has(out, k) && !_.has(prefixKey, v.prefix)) {
                    changed[k] = v;
                }
            });
            await Snippets.write(dirPath, out, changed);
            return changed;
        }
    }
    static write(dirPath, orig, changed) {
        const snippetPath = path.join(dirPath, Snippets.filename);
        const snippets = assignJSONWithComment(orig, changed);
        return writeJSONWithCommentsSync(snippetPath, snippets);
    }
}
export class Settings {
    static getDefaults() {
        return _.mapValues(_SETTINGS, (obj) => {
            return obj.default;
        });
    }
    static configEntries() {
        return _SETTINGS;
    }
    static defaults() {
        return { ...Settings.getDefaults() };
    }
    static defaultsChangeSet() {
        return _SETTINGS;
    }
}
//# sourceMappingURL=vscode.js.map