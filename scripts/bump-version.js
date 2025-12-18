#!/usr/bin/env node
/**
 * Version bump script for SailZen monorepo
 * 
 * Usage:
 *   node scripts/bump-version.js <version>
 *   node scripts/bump-version.js 0.2.0
 *   node scripts/bump-version.js patch|minor|major
 * 
 * This script updates the version in all package.json files across the monorepo.
 */

const fs = require('fs');
const path = require('path');

// All packages in the monorepo
const PACKAGES = [
  'packages/vscode_plugin/package.json',
  'packages/common-all/package.json',
  'packages/common-server/package.json',
  'packages/unified/package.json',
  'packages/engine-server/package.json',
  'packages/api_server/package.json',
  'packages/dendron_plugin_views/package.json',
  'packages/site/package.json',
];

function parseVersion(version) {
  const match = version.match(/^(\d+)\.(\d+)\.(\d+)$/);
  if (!match) return null;
  return {
    major: parseInt(match[1]),
    minor: parseInt(match[2]),
    patch: parseInt(match[3]),
  };
}

function bumpVersion(currentVersion, type) {
  const parsed = parseVersion(currentVersion);
  if (!parsed) {
    console.error(`Invalid current version: ${currentVersion}`);
    process.exit(1);
  }

  switch (type) {
    case 'major':
      return `${parsed.major + 1}.0.0`;
    case 'minor':
      return `${parsed.major}.${parsed.minor + 1}.0`;
    case 'patch':
      return `${parsed.major}.${parsed.minor}.${parsed.patch + 1}`;
    default:
      // Assume it's a specific version
      if (parseVersion(type)) {
        return type;
      }
      console.error(`Invalid version or bump type: ${type}`);
      console.error('Usage: node scripts/bump-version.js <version|patch|minor|major>');
      process.exit(1);
  }
}

function updatePackageJson(filePath, newVersion) {
  const fullPath = path.resolve(process.cwd(), filePath);
  
  if (!fs.existsSync(fullPath)) {
    console.warn(`  ⚠ File not found: ${filePath}`);
    return false;
  }

  try {
    const content = fs.readFileSync(fullPath, 'utf8');
    const pkg = JSON.parse(content);
    const oldVersion = pkg.version;
    pkg.version = newVersion;
    
    // Preserve formatting (2 spaces indent)
    fs.writeFileSync(fullPath, JSON.stringify(pkg, null, 2) + '\n');
    console.log(`  ✓ ${filePath}: ${oldVersion} → ${newVersion}`);
    return true;
  } catch (error) {
    console.error(`  ✗ Error updating ${filePath}: ${error.message}`);
    return false;
  }
}

function getCurrentVersion() {
  // Get version from the main plugin package
  const pluginPkgPath = path.resolve(process.cwd(), 'packages/vscode_plugin/package.json');
  try {
    const pkg = JSON.parse(fs.readFileSync(pluginPkgPath, 'utf8'));
    return pkg.version;
  } catch {
    return '0.0.0';
  }
}

function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.log('SailZen Version Bump Script');
    console.log('===========================');
    console.log('');
    console.log('Usage:');
    console.log('  node scripts/bump-version.js <version>   Set specific version (e.g., 0.2.0)');
    console.log('  node scripts/bump-version.js patch       Bump patch version (0.1.0 → 0.1.1)');
    console.log('  node scripts/bump-version.js minor       Bump minor version (0.1.0 → 0.2.0)');
    console.log('  node scripts/bump-version.js major       Bump major version (0.1.0 → 1.0.0)');
    console.log('');
    console.log(`Current version: ${getCurrentVersion()}`);
    process.exit(0);
  }

  const versionArg = args[0];
  const currentVersion = getCurrentVersion();
  const newVersion = bumpVersion(currentVersion, versionArg);

  console.log('');
  console.log('SailZen Version Bump');
  console.log('====================');
  console.log(`Updating all packages from ${currentVersion} to ${newVersion}`);
  console.log('');

  let successCount = 0;
  let failCount = 0;

  for (const pkgPath of PACKAGES) {
    if (updatePackageJson(pkgPath, newVersion)) {
      successCount++;
    } else {
      failCount++;
    }
  }

  console.log('');
  console.log(`Done! Updated ${successCount} packages${failCount > 0 ? `, ${failCount} failed` : ''}.`);
  console.log('');
  console.log('Next steps:');
  console.log('  1. Review the changes: git diff');
  console.log('  2. Build and test: pnpm plugin:build');
  console.log('  3. Package: pnpm plugin:package');
  console.log('  4. Commit: git add -A && git commit -m "chore: bump version to ' + newVersion + '"');
}

main();
