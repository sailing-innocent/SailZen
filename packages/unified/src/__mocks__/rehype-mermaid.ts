/**
 * Mock for rehype-mermaid
 * Avoids mermaid-isomorphic import.meta.resolve issues in Jest
 */
import type { Root } from "hast";

const rehypeMermaid = () => {
  return (tree: Root) => tree;
};

export default rehypeMermaid;
