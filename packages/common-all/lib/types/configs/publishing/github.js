import { z, schemaForType } from "../../../parse";
export var GithubEditViewModeEnum;
(function (GithubEditViewModeEnum) {
    GithubEditViewModeEnum["tree"] = "tree";
    GithubEditViewModeEnum["edit"] = "edit";
})(GithubEditViewModeEnum || (GithubEditViewModeEnum = {}));
export function genDefaultGithubConfig() {
    return {
        enableEditLink: true,
        editLinkText: "Edit this page on GitHub",
        editBranch: "main",
        editViewMode: GithubEditViewModeEnum.tree,
    };
}
const githubEditViewModeSchema = schemaForType()(z.union([
    z.literal(GithubEditViewModeEnum.tree),
    z.literal(GithubEditViewModeEnum.edit),
]));
export const githubSchema = schemaForType()(z.object({
    cname: z.string().optional(),
    enableEditLink: z.boolean().default(true),
    editLinkText: z.string().optional().default("Edit this page on GitHub"),
    editBranch: z.string().optional().default("main"),
    editViewMode: githubEditViewModeSchema
        .optional()
        .default(GithubEditViewModeEnum.tree),
    editRepository: z.string().optional(),
}));
//# sourceMappingURL=github.js.map