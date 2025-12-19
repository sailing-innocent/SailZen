#!/usr/bin/env node

/**
 * 构建脚本：自动构建指定包及其所有依赖包
 * 
 * 使用方法:
 *   node scripts/build-with-deps.js <package-name> [build-script]
 * 
 * 示例:
 *   node scripts/build-with-deps.js @saili/engine-server
 *   node scripts/build-with-deps.js @saili/engine-server buildCI
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PACKAGES_DIR = path.join(__dirname, '..', 'packages');

/**
 * 获取所有包的 package.json 信息
 */
function getAllPackages() {
  const packages = {};
  const packagesDir = PACKAGES_DIR;
  
  if (!fs.existsSync(packagesDir)) {
    throw new Error(`Packages directory not found: ${packagesDir}`);
  }
  
  const entries = fs.readdirSync(packagesDir, { withFileTypes: true });
  
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    
    const packagePath = path.join(packagesDir, entry.name, 'package.json');
    if (!fs.existsSync(packagePath)) continue;
    
    try {
      const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf-8'));
      if (packageJson.name) {
        packages[packageJson.name] = {
          name: packageJson.name,
          path: path.join(packagesDir, entry.name),
          dependencies: packageJson.dependencies || {},
          devDependencies: packageJson.devDependencies || {},
          scripts: packageJson.scripts || {}
        };
      }
    } catch (error) {
      console.warn(`Warning: Failed to parse ${packagePath}:`, error.message);
    }
  }
  
  return packages;
}

/**
 * 提取 workspace 依赖（以 workspace: 开头的依赖）
 */
function getWorkspaceDependencies(packageInfo) {
  const deps = new Set();
  
  // 检查 dependencies 和 devDependencies
  const allDeps = { ...packageInfo.dependencies, ...packageInfo.devDependencies };
  
  for (const [depName, depVersion] of Object.entries(allDeps)) {
    if (typeof depVersion === 'string' && depVersion.startsWith('workspace:')) {
      deps.add(depName);
    }
  }
  
  return Array.from(deps);
}

/**
 * 构建依赖图
 */
function buildDependencyGraph(packages) {
  const graph = {};
  const inDegree = {};
  
  // 初始化图
  for (const pkgName of Object.keys(packages)) {
    graph[pkgName] = [];
    inDegree[pkgName] = 0;
  }
  
  // 构建边
  for (const [pkgName, pkgInfo] of Object.entries(packages)) {
    const deps = getWorkspaceDependencies(pkgInfo);
    for (const dep of deps) {
      if (graph[dep]) {
        graph[dep].push(pkgName);
        inDegree[pkgName]++;
      }
    }
  }
  
  return { graph, inDegree };
}

/**
 * 拓扑排序：获取构建顺序（从依赖到被依赖）
 */
function getBuildOrder(targetPackage, packages) {
  const { graph, inDegree } = buildDependencyGraph(packages);
  
  // 从目标包开始，找到所有依赖
  const visited = new Set();
  const buildOrder = [];
  
  function collectDependencies(pkgName) {
    if (visited.has(pkgName)) return;
    visited.add(pkgName);
    
    const pkgInfo = packages[pkgName];
    if (!pkgInfo) return;
    
    const deps = getWorkspaceDependencies(pkgInfo);
    for (const dep of deps) {
      if (packages[dep] && !visited.has(dep)) {
        collectDependencies(dep);
      }
    }
    
    buildOrder.push(pkgName);
  }
  
  collectDependencies(targetPackage);
  
  return buildOrder;
}

/**
 * 确定构建脚本
 */
function determineBuildScript(packageName, buildScript, packages) {
  const pkgInfo = packages[packageName];
  if (!pkgInfo) {
    throw new Error(`Package not found: ${packageName}`);
  }
  
  // 如果指定了构建脚本，优先使用
  if (buildScript && pkgInfo.scripts[buildScript]) {
    return buildScript;
  }
  
  // 按优先级尝试：buildCI -> build -> compile
  const scriptPriority = ['buildCI', 'build', 'compile'];
  for (const script of scriptPriority) {
    if (pkgInfo.scripts[script]) {
      return script;
    }
  }
  
  throw new Error(`No build script found for ${packageName}. Available scripts: ${Object.keys(pkgInfo.scripts).join(', ')}`);
}

/**
 * 构建单个包
 */
function buildPackage(packageName, buildScript, packages) {
  const pkgInfo = packages[packageName];
  if (!pkgInfo) {
    throw new Error(`Package not found: ${packageName}`);
  }
  
  // 确定构建脚本
  const script = determineBuildScript(packageName, buildScript, packages);
  
  console.log(`\n📦 Building ${packageName} (script: ${script})...`);
  
  try {
    execSync(`pnpm --filter "${packageName}" run ${script}`, {
      stdio: 'inherit',
      cwd: path.join(__dirname, '..')
    });
    console.log(`✅ Successfully built ${packageName}`);
  } catch (error) {
    console.error(`❌ Failed to build ${packageName}`);
    throw error;
  }
}

/**
 * 主函数
 */
function main() {
  const args = process.argv.slice(2);
  
  if (args.length === 0) {
    console.error('Usage: node scripts/build-with-deps.js <package-name> [build-script]');
    console.error('\nExamples:');
    console.error('  node scripts/build-with-deps.js @saili/engine-server');
    console.error('  node scripts/build-with-deps.js @saili/engine-server buildCI');
    console.error('  node scripts/build-with-deps.js @saili/vscode_plugin build');
    process.exit(1);
  }
  
  const targetPackage = args[0];
  const buildScript = args[1]; // 可选，默认为 buildCI
  
  console.log(`🔍 Analyzing dependencies for ${targetPackage}...`);
  
  try {
    // 获取所有包信息
    const packages = getAllPackages();
    
    // 检查目标包是否存在
    if (!packages[targetPackage]) {
      console.error(`\n❌ Package not found: ${targetPackage}`);
      console.error('\nAvailable packages:');
      for (const pkgName of Object.keys(packages).sort()) {
        console.error(`  - ${pkgName}`);
      }
      process.exit(1);
    }
    
    // 获取构建顺序
    const buildOrder = getBuildOrder(targetPackage, packages);
    
    console.log(`\n📋 Build order:`);
    buildOrder.forEach((pkg, index) => {
      const marker = pkg === targetPackage ? '🎯' : '  ';
      console.log(`${marker} ${index + 1}. ${pkg}`);
    });
    
    // 按顺序构建
    console.log(`\n🚀 Starting build process...\n`);
    for (const pkg of buildOrder) {
      // 只有目标包使用指定的构建脚本，依赖包使用默认的智能选择
      const scriptToUse = pkg === targetPackage ? buildScript : undefined;
      buildPackage(pkg, scriptToUse, packages);
    }
    
    console.log(`\n✨ All packages built successfully!`);
    
  } catch (error) {
    console.error(`\n❌ Build failed:`, error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { getAllPackages, getBuildOrder, buildPackage };

