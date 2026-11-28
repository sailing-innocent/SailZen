/**
 * No-op implementation of rehype-mermaid
 * Replaces rehype-mermaid to avoid mermaid-isomorphic dependencies
 * (playwright-core, import.meta.resolve issues)
 *
 * This is a pass-through plugin that does nothing, effectively disabling mermaid rendering.
 * If mermaid support is needed in the future, consider using a different approach
 * that doesn't require playwright or import.meta.resolve.
 */
import type { Root } from "hast";
/**
 * No-op rehype plugin for mermaid
 * Simply returns the tree unchanged, effectively disabling mermaid rendering
 */
declare const rehypeMermaidNoOp: () => (tree: Root) => Root;
export default rehypeMermaidNoOp;
