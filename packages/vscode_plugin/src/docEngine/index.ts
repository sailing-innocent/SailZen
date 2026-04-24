export {
  resolveProfile,
  extractCitations,
  extractAssetRefs,
  extractTableRefs,
  extractAlgorithmRefs,
  extractMathEnvs,
  extractConditionals,
} from "./profileResolver";
export { assembleDocument } from "./documentAssembler";
export { generateLatex } from "./latexBackend";
export { generateTypst } from "./typstBackend";
export { generateMarkdown } from "./markdownBackend";
export {
  renderTemplate,
  resolveTemplateVars,
  getBuiltinTemplate,
  listBuiltinTemplates,
  getTemplate,
  listTemplates,
  BUILTIN_TEMPLATES,
} from "./templateEngine";
export {
  loadExternalTemplate,
  resolveTemplateDir,
  listExternalTemplates,
  renderSkeleton,
  renderExternalTemplate,
} from "./templateLoader";
export type { ExternalTemplate } from "./templateLoader";
export type { ResolvedAsset } from "@saili/common-all";
