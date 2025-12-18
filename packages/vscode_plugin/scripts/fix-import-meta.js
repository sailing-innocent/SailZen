#!/usr/bin/env node
// Post-build script to fix import.meta.url in CommonJS bundle
const fs = require('fs');
const path = require('path');

const distFile = path.join(__dirname, '../dist/extension.js');

if (!fs.existsSync(distFile)) {
  console.error('dist/extension.js not found');
  process.exit(1);
}

let content = fs.readFileSync(distFile, 'utf8');

// Get the actual file path for import.meta.url polyfill
const extensionPath = path.resolve(__dirname, '../dist/extension.js');
const fileUrl = 'file://' + (process.platform === 'win32' ? '/' : '') + extensionPath.replace(/\\/g, '/');

// Replace all instances of import_meta.url with the polyfill
// First, add polyfill function at the beginning if not present
if (!content.includes('__import_meta_url_polyfill')) {
  const polyfillCode = `
(function() {
  const { createRequire } = require('module');
  const path = require('path');
  const { fileURLToPath } = require('url');
  
  // Get the actual extension.js file path
  const extensionPath = ${JSON.stringify(extensionPath)};
  const fileUrl = ${JSON.stringify(fileUrl)};
  
  // Polyfill for import.meta.url
  function getImportMetaUrl() {
    // Try to get the caller's file path from stack trace
    const stack = new Error().stack;
    if (stack) {
      const match = stack.match(/at .* \\((.*):\\d+:\\d+\\)/);
      if (match && match[1]) {
        const callerPath = path.resolve(match[1]);
        return 'file://' + (process.platform === 'win32' ? '/' : '') + callerPath.replace(/\\\\/g, '/');
      }
    }
    return fileUrl;
  }
  
  // Replace all var import_meta = {}; with polyfilled version
  const originalEval = eval;
  global.eval = function(code) {
    if (typeof code === 'string') {
      code = code.replace(/var (import_meta\\d*)\\s*=\\s*\\{\\};/g, (match, varName) => {
        return \`var \${varName} = { url: getImportMetaUrl(), resolve: function(specifier, parentURL) { const { createRequire } = require('module'); const path = require('path'); const { fileURLToPath } = require('url'); try { if (parentURL) { const parentPath = parentURL.startsWith('file://') ? fileURLToPath(parentURL) : parentURL; return createRequire(parentPath).resolve(specifier); } return createRequire(getImportMetaUrl().replace('file://', '')).resolve(specifier); } catch(e) { if (specifier.startsWith('.')) { const parentDir = parentURL ? (parentURL.startsWith('file://') ? path.dirname(fileURLToPath(parentURL)) : path.dirname(parentURL)) : path.dirname(fileURLToPath(getImportMetaUrl())); return path.resolve(parentDir, specifier); } throw e; } } };\`;
      });
    }
    return originalEval.call(this, code);
  };
})();
`;
  content = polyfillCode.trim() + '\n' + content;
}

// Replace all var import_meta = {}; with version that has url property
content = content.replace(/var (import_meta\d*)\s*=\s*\{\};/g, (match, varName) => {
  return `var ${varName} = { url: ${JSON.stringify(fileUrl)}, resolve: function(specifier, parentURL) { const { createRequire } = require('module'); const path = require('path'); const { fileURLToPath } = require('url'); try { if (parentURL) { const parentPath = parentURL.startsWith('file://') ? fileURLToPath(parentURL) : parentURL; return createRequire(parentPath).resolve(specifier); } return createRequire(__filename).resolve(specifier); } catch(e) { if (specifier.startsWith('.')) { const parentDir = parentURL ? (parentURL.startsWith('file://') ? path.dirname(fileURLToPath(parentURL)) : path.dirname(parentURL)) : __dirname; return path.resolve(parentDir, specifier); } throw e; } } };`;
});

fs.writeFileSync(distFile, content, 'utf8');
console.log('Fixed import.meta.url polyfill');
