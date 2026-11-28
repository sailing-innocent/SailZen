import { assertUnreachable, ConfigUtils, SailError, ERROR_STATUS, getSlugger, ProcFlavor, } from "@saili/common-all";
// @ts-ignore
import rehypePrism from "@mapbox/rehype-prism";
import _ from "lodash";
import link from "rehype-autolink-headings";
import math from "remark-math";
// @ts-ignore
import katex from "rehype-katex";
import raw from "rehype-raw";
import slug from "rehype-slug";
import rehypeStringify from "rehype-stringify";
// Use no-op version to avoid mermaid-isomorphic dependencies (playwright, import.meta.resolve)
import rehypeMermaid from "./rehype/mermaid-noop";
import { remark } from "remark";
import { abbrPlugin } from "./remark/abbr";
import remarkGfm from "remark-gfm";
import frontmatterPlugin from "remark-frontmatter";
import remarkParse from "remark-parse";
import remark2rehype from "remark-rehype";
// import rehypeWrap from "rehype-wrap";
import { wrap } from "./rehype/wrap";
import { hierarchies } from "./remark";
import { backlinks } from "./remark/backlinks";
import { backlinksHover } from "./remark/backlinksHover";
import { blockAnchors } from "./remark/blockAnchors";
import { sailHoverPreview } from "./remark/sailPreview";
import { sailPub } from "./remark/sailPub";
import { extendedImage } from "./remark/extendedImage";
import { hashtags } from "./remark/hashtag";
import { noteRefs } from "./remark/noteRefs";
import { zdocTags } from "./remark/zdocTags";
import { wikiLinks } from "./remark/wikiLinks";
import { sailzenCite } from "./remark/sailzenCite";
import { sailzenFigure } from "./remark/sailzenFigure";
import { sailzenBlocks } from "./remark/sailzenBlocks";
import { pageElements } from "./remark/pageElements";
import { SailASTDest } from "./types";
import path from "path";
export { ProcFlavor };
/**
 * What mode a processor should run in
 */
export var ProcMode;
(function (ProcMode) {
    /**
     * Expect no properties from {@link ProcDataFullV5} when running the processor
     */
    ProcMode["NO_DATA"] = "NO_DATA";
    /**
     * Expect all properties from {@link ProcDataFullV5} when running the processor
     */
    ProcMode["FULL"] = "all data";
    /**
     * Running processor in import mode. Notes don't exist. Used for import pods like {@link MarkdownPod}
     * where notes don't exist in the engine prior to import.
     */
    ProcMode["IMPORT"] = "IMPORT";
})(ProcMode || (ProcMode = {}));
function checkProps({ requiredProps, data, }) {
    const hasAllProps = _.map(requiredProps, (prop) => {
        // @ts-ignore
        return !_.isUndefined(data[prop]);
    });
    if (!_.every(hasAllProps)) {
        // @ts-ignore
        const missing = _.filter(requiredProps, (prop) => 
        // @ts-ignore
        _.isUndefined(data[prop]));
        return { valid: false, missing };
    }
    return { valid: true };
}
let REF_CACHE;
export class MDUtilsV5 {
    static getRefsRoot = (wsRoot) => {
        return path.join(wsRoot, "build", "refs");
    };
    /**
     * Write ref
     * @param param1
     */
    static cacheRefId({ refId, mdast, prettyHAST, }) {
        if (REF_CACHE === undefined) {
            REF_CACHE = {};
        }
        const idString = getRefId(refId);
        const payload = { node: mdast, refId, prettyHAST };
        REF_CACHE[idString] = payload;
    }
    static clearRefCache() {
        REF_CACHE = undefined;
    }
    static getRefCache() {
        if (!REF_CACHE) {
            return {};
        }
        return REF_CACHE;
    }
    static getProcOpts(proc) {
        const _data = proc.data("sailProcOptsv5");
        return (_data || {});
    }
    static getProcData(proc) {
        const _data = proc.data("sailProcDatav5");
        return (_data || {});
    }
    static setNoteRefLvl(proc, lvl) {
        return this.setProcData(proc, { noteRefLvl: lvl });
    }
    static setProcData(proc, opts) {
        const _data = proc.data("sailProcDatav5") || {};
        return proc.data("sailProcDatav5", { ..._data, ...opts });
    }
    static setProcOpts(proc, opts) {
        const _data = proc.data("sailProcOptsv5") || {};
        return proc.data("sailProcOptsv5", { ..._data, ...opts });
    }
    static isV5Active(proc) {
        return !_.isUndefined(this.getProcOpts(proc).mode);
    }
    static shouldApplyPublishingRules(proc) {
        return (this.getProcData(proc).dest === SailASTDest.HTML &&
            this.getProcOpts(proc).flavor === ProcFlavor.PUBLISHING);
    }
    static getFM(opts) {
        const { note } = opts;
        const custom = note.custom ? note.custom : undefined;
        return {
            ...custom,
            id: note.id,
            title: note.title,
            desc: note.desc,
            created: note.created,
            updated: note.updated,
        };
    }
    /**
     * Used for processing a Sail markdown note
     */
    static _procRemark(opts, data) {
        const errors = [];
        opts = _.defaults(opts, { flavor: ProcFlavor.REGULAR });
        let proc = remark()
            .use(remarkParse, { gfm: true })
            .use(frontmatterPlugin, ["yaml"])
            .use(abbrPlugin)
            .use({ settings: { listItemIndent: "one", fences: true, bullet: "-" } })
            .use(noteRefs)
            .use(blockAnchors)
            .use(hashtags)
            .use(zdocTags)
            .use(extendedImage)
            .use(pageElements)
            .use(remarkGfm)
            .use(backlinksHover, data.backlinkHoverOpts)
            .data("errors", errors);
        // Add SailZen Doc syntax extensions for export/preview modes
        if (data.dest === SailASTDest.DOC_EXPORT ||
            data.dest === SailASTDest.DOC_PREVIEW) {
            proc = proc
                .use(sailzenCite)
                .use(sailzenFigure)
                .use(sailzenBlocks);
        }
        //do not convert wikilinks if convertLinks set to false. Used by gdoc export pod. It uses HTMLPublish pod to do the md-->html conversion
        if (_.isUndefined(data.wikiLinksOpts?.convertLinks) ||
            data.wikiLinksOpts?.convertLinks) {
            proc = proc.use(wikiLinks, data.wikiLinksOpts);
        }
        // set options and do validation
        proc = this.setProcOpts(proc, opts);
        switch (opts.mode) {
            case ProcMode.FULL:
                {
                    if (_.isUndefined(data)) {
                        throw SailError.createFromStatus({
                            status: ERROR_STATUS.INVALID_CONFIG,
                            message: `data is required when not using raw proc`,
                        });
                    }
                    const requiredProps = ["vault", "fname", "dest"];
                    const resp = checkProps({ requiredProps, data });
                    if (!resp.valid) {
                        throw SailError.createFromStatus({
                            status: ERROR_STATUS.INVALID_CONFIG,
                            message: `missing required fields in data. ${resp.missing.join(" ,")} missing`,
                        });
                    }
                    const note = data.noteToRender;
                    if (!_.isUndefined(note)) {
                        proc = proc.data("fm", this.getFM({ note }));
                    }
                    this.setProcData(proc, data);
                    // NOTE: order matters. this needs to appear before `sailPub`
                    if (data.dest === SailASTDest.HTML) {
                        //do not convert backlinks, children if convertLinks set to false. Used by gdoc export pod. It uses HTMLPublish pod to do the md-->html conversion
                        if (_.isUndefined(data.wikiLinksOpts?.convertLinks) ||
                            data.wikiLinksOpts?.convertLinks) {
                            proc = proc.use(hierarchies).use(backlinks);
                        }
                    }
                    // Add flavor specific plugins. These need to come before `sailPub`
                    // to fix extended image URLs before they get converted to HTML
                    if (opts.flavor === ProcFlavor.PREVIEW) {
                        // No extra plugins needed for the preview right now. We used to
                        // need a plugin to rewrite URLs to get the engine to proxy images,
                        // but now that's done by the
                        // [[PreviewPanel|../packages/plugin-core/src/components/views/PreviewPanel.ts#^preview-rewrites-images]]
                    }
                    if (opts.flavor === ProcFlavor.HOVER_PREVIEW ||
                        opts.flavor === ProcFlavor.BACKLINKS_PANEL_HOVER) {
                        proc = proc.use(sailHoverPreview);
                    }
                    // add additional plugins
                    const isNoteRef = !_.isUndefined(data.noteRefLvl);
                    let insertTitle;
                    if (isNoteRef || opts.flavor === ProcFlavor.BACKLINKS_PANEL_HOVER) {
                        insertTitle = false;
                    }
                    else {
                        const shouldApplyPublishRules = MDUtilsV5.shouldApplyPublishingRules(proc);
                        insertTitle = ConfigUtils.getEnableFMTitle(data.config, shouldApplyPublishRules);
                    }
                    const config = data.config;
                    const publishingConfig = ConfigUtils.getPublishing(config);
                    const assetsPrefix = publishingConfig.assetsPrefix;
                    proc = proc.use(sailPub, {
                        insertTitle,
                        transformNoPublish: opts.flavor === ProcFlavor.PUBLISHING,
                        ...data.publishOpts,
                    });
                    const shouldApplyPublishRules = MDUtilsV5.shouldApplyPublishingRules(proc);
                    if (ConfigUtils.getEnableKatex(config, shouldApplyPublishRules)) {
                        proc = proc.use(math);
                    }
                    // Add remaining flavor specific plugins
                    if (opts.flavor === ProcFlavor.PUBLISHING) {
                        const prefix = assetsPrefix ? assetsPrefix + "/notes/" : "/notes/";
                        proc = proc.use(sailPub, {
                            wikiLinkOpts: {
                                prefix,
                            },
                        });
                    }
                }
                break;
            case ProcMode.IMPORT: {
                const requiredProps = ["vault", "dest"];
                const resp = checkProps({ requiredProps, data });
                if (!resp.valid) {
                    throw SailError.createFromStatus({
                        status: ERROR_STATUS.INVALID_CONFIG,
                        message: `missing required fields in data. ${resp.missing.join(" ,")} missing`,
                    });
                }
                // backwards compatibility, default to v4 values
                this.setProcData(proc, data);
                // add additional plugins
                const config = data.config;
                const shouldApplyPublishRules = MDUtilsV5.shouldApplyPublishingRules(proc);
                if (ConfigUtils.getEnableKatex(config, shouldApplyPublishRules)) {
                    proc = proc.use(math);
                }
                break;
            }
            case ProcMode.NO_DATA:
                break;
            default:
                assertUnreachable(opts.mode);
        }
        return proc;
    }
    static _procRehype(opts, data) {
        const pRemarkParse = this.procRemarkParse(opts, {
            ...data,
            dest: SailASTDest.HTML,
        });
        // add additional plugin for publishing
        let pRehype = pRemarkParse
            .use(remark2rehype, { allowDangerousHtml: true })
            .use(rehypePrism, { ignoreMissing: true })
            .use(rehypeMermaid, { strategy: "pre-mermaid" })
            .use(wrap, { selector: "table", wrapper: "div.table-responsive" })
            .use(raw)
            .use(slug);
        // apply plugins enabled by config
        const shouldApplyPublishRules = MDUtilsV5.shouldApplyPublishingRules(pRehype);
        const { insideNoteRef } = data;
        if (ConfigUtils.getEnableKatex(data.config, shouldApplyPublishRules)) {
            pRehype = pRehype.use(katex);
        }
        // apply publishing specific things, don't use anchor headings in note refs
        if (shouldApplyPublishRules && !insideNoteRef) {
            pRehype = pRehype.use(link, {
                behavior: "append",
                properties: {
                    "aria-hidden": "true",
                    class: "anchor-heading icon-link",
                },
                content: {
                    type: "text",
                    // @ts-ignore
                    value: "",
                },
            });
        }
        return pRehype;
    }
    static procRemarkFull(data, opts) {
        return this._procRemark({
            mode: opts?.mode || ProcMode.FULL,
            flavor: opts?.flavor || ProcFlavor.REGULAR,
        }, data);
    }
    /**
     * Parse Sail Markdown Note. No compiler is attached.
     * @param opts
     * @param data
     * @returns
     */
    static procRemarkParse(opts, data) {
        return this._procRemark({ ...opts, parseOnly: true }, data);
    }
    /**
     *
     * Warning! When using a no-data parser, any user configuration will not be
     * available. Avoid using it unless you are sure that the user configuration
     * has no effect on what you are doing.
     */
    static procRemarkParseNoData(opts, data) {
        // ProcMode.NO_DATA doesn't need config so we generate default to pass compilation
        const withConfig = { ...data, config: ConfigUtils.genDefaultConfig() };
        return this._procRemark({ ...opts, parseOnly: true, mode: ProcMode.NO_DATA }, withConfig);
    }
    static procRemarkParseFull(opts, data) {
        return this._procRemark({ ...opts, parseOnly: true, mode: ProcMode.FULL }, data);
    }
    static procRehypeFull(data, opts) {
        const proc = this._procRehype({ mode: ProcMode.FULL, parseOnly: false, flavor: opts?.flavor }, data);
        return proc.use(rehypeStringify);
    }
}
export const getRefId = ({ link, id }) => {
    const { anchorStart, anchorEnd, anchorStartOffset } = _.defaults(link.data, {
        anchorStartOffset: 0,
    });
    const slug = getSlugger();
    return slug.slug([id, anchorStart, anchorEnd, anchorStartOffset].join("-"));
};
//# sourceMappingURL=utilsv5.js.map