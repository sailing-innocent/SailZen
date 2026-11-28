/**
 * No-op rehype plugin for mermaid
 * Simply returns the tree unchanged, effectively disabling mermaid rendering
 */
const rehypeMermaidNoOp = () => {
    return (tree) => {
        // Do nothing - just pass through the tree
        // Mermaid diagrams will remain as code blocks or pre-mermaid divs
        return tree;
    };
};
export default rehypeMermaidNoOp;
//# sourceMappingURL=mermaid-noop.js.map