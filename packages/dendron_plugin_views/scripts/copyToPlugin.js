#!/usr/bin/env node
/**
 * Copy built assets to vscode_plugin
 * This script copies the build output to both assets (for dev) and dist (for production)
 */

const fs = require("fs");
const path = require("path");

const SOURCE_DIR = path.resolve(__dirname, "../build");
const PLUGIN_DIR = path.resolve(__dirname, "../../vscode_plugin");
const ASSETS_DIR = path.join(PLUGIN_DIR, "assets");
const DIST_DIR = path.join(PLUGIN_DIR, "dist");

/**
 * Recursively copy directory
 */
function copyDir(src, dest) {
  // Create destination directory if it doesn't exist
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }

  const entries = fs.readdirSync(src, { withFileTypes: true });

  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
      console.log(`  Copied: ${entry.name}`);
    }
  }
}

/**
 * Main function
 */
function main() {
  console.log("=== Copying dendron_plugin_views build to vscode_plugin ===\n");

  // Check if source directory exists
  if (!fs.existsSync(SOURCE_DIR)) {
    console.error(`Error: Source directory not found: ${SOURCE_DIR}`);
    console.error("Please run 'pnpm build' first.");
    process.exit(1);
  }

  // Copy to assets (for development)
  console.log(`Copying to assets (dev): ${ASSETS_DIR}`);
  copyDir(SOURCE_DIR, ASSETS_DIR);
  console.log("");

  // Copy to dist (for production)
  console.log(`Copying to dist (prod): ${DIST_DIR}`);
  copyDir(SOURCE_DIR, DIST_DIR);
  console.log("");

  console.log("✅ Copy completed successfully!");
}

main();
