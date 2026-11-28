#!/usr/bin/env node
/**
 * Copy Prisma-related files from engine-server to vscode_plugin dist directory
 * This includes:
 * - prisma-shim.js
 * - adm-zip.js
 * - generated-prisma-client directory (if exists)
 */
const fs = require('fs');
const path = require('path');

const engineServerDir = path.join(__dirname, '../../engine-server');
const distDir = path.join(__dirname, '../dist');

// Ensure dist directory exists
if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

// Files to copy from engine-server/lib/drivers
const filesToCopy = ['prisma-shim.js', 'adm-zip.js'];

// Try lib directory first, then fallback to src directory
const possibleSourceDirs = [
  path.join(engineServerDir, 'lib', 'drivers'),
  path.join(engineServerDir, 'src', 'drivers'),
];

let sourceDir = null;
for (const dir of possibleSourceDirs) {
  if (fs.existsSync(dir)) {
    sourceDir = dir;
    break;
  }
}

if (!sourceDir) {
  console.error(`Error: Could not find engine-server drivers directory. Tried: ${possibleSourceDirs.join(', ')}`);
  console.error(`Please run 'pnpm --filter=@saili/engine-server run build' first.`);
  process.exit(1);
}

console.log(`Copying Prisma assets from ${sourceDir} to ${distDir}`);

// Copy individual files
for (const file of filesToCopy) {
  const srcFile = path.join(sourceDir, file);
  const destFile = path.join(distDir, file);
  
  if (fs.existsSync(srcFile)) {
    fs.copyFileSync(srcFile, destFile);
    console.log(`✓ Copied ${file}`);
  } else {
    console.warn(`⚠ Warning: ${file} not found at ${srcFile}`);
  }
}

// Copy generated-prisma-client directory if it exists
// Try multiple possible locations
const prismaClientPossibleSrcs = [
  path.join(sourceDir, 'generated-prisma-client'),
  path.join(engineServerDir, 'src', 'drivers', 'generated-prisma-client'),
  path.join(engineServerDir, 'lib', 'drivers', 'generated-prisma-client'),
];
const prismaClientDest = path.join(distDir, 'generated-prisma-client');

let prismaClientCopied = false;
for (const prismaClientSrc of prismaClientPossibleSrcs) {
  if (fs.existsSync(prismaClientSrc)) {
    // Use fs-extra if available, otherwise use recursive copy
    try {
      const fse = require('fs-extra');
      fse.copySync(prismaClientSrc, prismaClientDest, { overwrite: true });
      console.log(`✓ Copied generated-prisma-client directory from ${prismaClientSrc}`);
      prismaClientCopied = true;
      break;
    } catch (e) {
      // Fallback: manual recursive copy
      function copyRecursive(src, dest) {
        if (!fs.existsSync(dest)) {
          fs.mkdirSync(dest, { recursive: true });
        }
        const entries = fs.readdirSync(src, { withFileTypes: true });
        for (const entry of entries) {
          const srcPath = path.join(src, entry.name);
          const destPath = path.join(dest, entry.name);
          if (entry.isDirectory()) {
            copyRecursive(srcPath, destPath);
          } else {
            fs.copyFileSync(srcPath, destPath);
          }
        }
      }
      copyRecursive(prismaClientSrc, prismaClientDest);
      console.log(`✓ Copied generated-prisma-client directory (manual) from ${prismaClientSrc}`);
      prismaClientCopied = true;
      break;
    }
  }
}

if (!prismaClientCopied) {
  console.warn(`⚠ Warning: generated-prisma-client not found at any of: ${prismaClientPossibleSrcs.join(', ')}`);
  console.warn(`  Note: Prisma client will be downloaded at runtime if needed.`);
}

console.log('✓ Prisma assets copy completed');
