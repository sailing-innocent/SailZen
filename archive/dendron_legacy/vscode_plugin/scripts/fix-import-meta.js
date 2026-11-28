#!/usr/bin/env node
// Post-build script to fix import.meta.url in CommonJS bundle
// esbuild converts import.meta.url to var import_meta = {}; when bundling to CommonJS
// This script replaces it with a proper polyfill
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const distFile = path.join(__dirname, '../dist/extension.js');

if (!fs.existsSync(distFile)) {
  console.error('dist/extension.js not found');
  process.exit(1);
}

let content = fs.readFileSync(distFile, 'utf8');

// Get the actual file path for import.meta.url polyfill
const extensionPath = path.resolve(__dirname, '../dist/extension.js');
const fileUrl = pathToFileURL(extensionPath).href;

// Replace all var import_meta = {}; with version that has url property
// This is needed because esbuild creates empty import_meta objects
const importMetaPattern = /var (import_meta\d*)\s*=\s*\{\};/g;
const hasImportMeta = importMetaPattern.test(content);

if (hasImportMeta) {
  // Reset regex lastIndex
  importMetaPattern.lastIndex = 0;
  
  content = content.replace(importMetaPattern, (match, varName) => {
    return `var ${varName} = { url: ${JSON.stringify(fileUrl)} };`;
  });
  
  fs.writeFileSync(distFile, content, 'utf8');
  console.log('Fixed import.meta.url polyfill');
} else {
  console.log('No import.meta references found, skipping fix');
}
