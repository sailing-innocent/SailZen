/**
 * Mock for rehype-mermaid
 * Avoids mermaid-isomorphic import.meta.resolve issues in Jest
 */
import type { Root } from "hast";
declare const rehypeMermaid: () => (tree: Root) => Root;
export default rehypeMermaid;
