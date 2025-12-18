/**
 * Mock data for standalone development without VSCode and backend API
 * This allows developers to work on UI components independently
 */

import { NoteProps, DVault } from "@saili/common-all";

/**
 * Sample vault configuration
 */
export const mockVault: DVault = {
  fsPath: "vault",
  name: "main",
};

/**
 * Sample note for preview testing
 */
export const mockNote: NoteProps = {
  id: "mock-note-1",
  fname: "sample.note",
  title: "Sample Note",
  desc: "This is a sample note for development",
  created: Date.now(),
  updated: Date.now(),
  vault: mockVault,
  parent: null,
  children: [],
  body: "# Sample Content\n\nThis is the body of the sample note.",
  type: "note",
  custom: {},
  contentHash: "mock-hash-123",
  links: [],
  anchors: {},
  data: {},
};

/**
 * Sample rendered HTML for preview testing
 * This mimics what the backend API would return
 */
export const mockPreviewHTML = `
<div class="dendron-note-preview">
  <h1>Sample Note Preview</h1>
  <p>This is a <strong>mock preview</strong> for standalone development.</p>
  
  <h2>Features</h2>
  <ul>
    <li>Supports <em>italic</em> and <strong>bold</strong> text</li>
    <li>Code blocks with syntax highlighting</li>
    <li>Links and references</li>
  </ul>
  
  <h3>Code Example</h3>
  <pre><code class="language-typescript">function hello(name: string): string {
  return \`Hello, \${name}!\`;
}

console.log(hello("Dendron"));
</code></pre>

  <h3>Table Example</h3>
  <table>
    <thead>
      <tr>
        <th>Feature</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Preview</td>
        <td>✅ Working</td>
      </tr>
      <tr>
        <td>Calendar</td>
        <td>✅ Working</td>
      </tr>
    </tbody>
  </table>

  <blockquote>
    <p>This is a blockquote for testing styles.</p>
  </blockquote>
</div>
`;

/**
 * Mock calendar data for DendronCalendarPanel
 */
export const mockCalendarData = {
  dailyNotes: [
    { date: "2024-01-15", noteId: "daily.2024.01.15" },
    { date: "2024-01-16", noteId: "daily.2024.01.16" },
    { date: "2024-01-17", noteId: "daily.2024.01.17" },
  ],
};

/**
 * Mock workspace configuration
 */
export const mockWorkspaceProps = {
  url: "http://localhost:3005",
  ws: "E:\\ws\\repos\\SailDendron\\test-workspace",
  browser: true,
  theme: "dark",
};
