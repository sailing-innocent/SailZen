export {
  pageElements,
  parseSailElem,
  SAIL_ELEM_TAG,
  SAIL_ELEM_KEY_ATTR,
} from "./remarkPageElements";
export type { ParsedSailElem } from "./remarkPageElements";
export {
  PageElementRegistry,
  getDefaultPageElementRegistry,
  resetDefaultPageElementRegistry,
  PAGE_ELEMENT_KEY_REGEX,
  PAGE_ELEMENT_PREFIX_KEY,
  PAGE_ELEMENT_POSTFIX_KEY,
  PAGE_ELEMENT_HELP_KEY,
} from "./registry";
export {
  renderPageElementHelp,
  renderPageElementError,
  escapeHtml,
} from "./render";
export type {
  NotePageElementProvider,
  PageElementArgs,
  PageElementRenderContext,
  PageElementsPluginOpts,
} from "./types";
