#!/usr/bin/env node

/**
 * 依赖升级脚本：将工作区内所有 JS/TS 包的依赖升级到最新版本
 *
 * 使用方法:
 *   node scripts/update-all.js [options] [package-name]
 *
 * 示例:
 *   node scripts/update-all.js                # 升级所有包
 *   node scripts/update-all.js @saili/common-all  # 仅升级指定包
 *   node scripts/update-all.js --dry-run      # 预览变更，不执行
 *   node scripts/update-all.js --continue     # 遇到错误继续处理下一个包
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT_DIR = path.join(__dirname, '..');
const PACKAGES_DIR = path.join(ROOT_DIR, 'packages');

/**
 * 解析命令行参数
 */
function parseArgs(argv) {
  const args = argv.slice(2);
  const options = {
    dryRun: false,
    continueOnError: false,
    targetPackage: null,
  };

  const positional = [];
  for (const arg of args) {
    if (arg === '--dry-run' || arg === '-d') {
      options.dryRun = true;
    } else if (arg === '--continue' || arg === '-c') {
      options.continueOnError = true;
    } else if (arg === '--help' || arg === '-h') {
      printUsage();
      process.exit(0);
    } else if (arg.startsWith('-')) {
      console.error(`❌ Unknown option: ${arg}`);
      printUsage();
      process.exit(1);
    } else {
      positional.push(arg);
    }
  }

  if (positional.length > 1) {
    console.error('❌ Too many positional arguments. Only one package-name is allowed.');
    printUsage();
    process.exit(1);
  }
  options.targetPackage = positional[0] || null;

  return options;
}

function printUsage() {
  console.log(`Usage: node scripts/update-all.js [options] [package-name]

Options:
  --dry-run, -d    预览将要升级的包，不执行 pnpm update
  --continue, -c   某个包升级失败时继续处理后续包
  --help, -h       显示帮助信息

Examples:
  node scripts/update-all.js
  node scripts/update-all.js @saili/common-all
  node scripts/update-all.js --dry-run`);
}

/**
 * 获取所有包的 package.json 信息（包含根目录）
 */
function getAllPackages() {
  const packages = {};

  // 根目录
  const rootPackagePath = path.join(ROOT_DIR, 'package.json');
  if (fs.existsSync(rootPackagePath)) {
    const rootPackageJson = JSON.parse(fs.readFileSync(rootPackagePath, 'utf-8'));
    packages[rootPackageJson.name || '@saili/sailzen'] = {
      name: rootPackageJson.name || '@saili/sailzen',
      path: ROOT_DIR,
      isRoot: true,
      dependencies: rootPackageJson.dependencies || {},
      devDependencies: rootPackageJson.devDependencies || {},
      peerDependencies: rootPackageJson.peerDependencies || {},
    };
  }

  if (!fs.existsSync(PACKAGES_DIR)) {
    return packages;
  }

  const entries = fs.readdirSync(PACKAGES_DIR, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;

    const packagePath = path.join(PACKAGES_DIR, entry.name, 'package.json');
    if (!fs.existsSync(packagePath)) continue;

    try {
      const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf-8'));
      if (packageJson.name) {
        packages[packageJson.name] = {
          name: packageJson.name,
          path: path.join(PACKAGES_DIR, entry.name),
          isRoot: false,
          dependencies: packageJson.dependencies || {},
          devDependencies: packageJson.devDependencies || {},
          peerDependencies: packageJson.peerDependencies || {},
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
  const allDeps = {
    ...packageInfo.dependencies,
    ...packageInfo.devDependencies,
    ...packageInfo.peerDependencies,
  };

  for (const [depName, depVersion] of Object.entries(allDeps)) {
    if (typeof depVersion === 'string' && depVersion.startsWith('workspace:')) {
      deps.add(depName);
    }
  }

  return Array.from(deps);
}

/**
 * 提取 catalog 依赖（以 catalog: 开头的依赖）
 */
function getCatalogDependencies(packageInfo) {
  const deps = new Set();
  const allDeps = {
    ...packageInfo.dependencies,
    ...packageInfo.devDependencies,
    ...packageInfo.peerDependencies,
  };

  for (const [depName, depVersion] of Object.entries(allDeps)) {
    if (typeof depVersion === 'string' && depVersion.startsWith('catalog:')) {
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

  for (const pkgName of Object.keys(packages)) {
    graph[pkgName] = [];
    inDegree[pkgName] = 0;
  }

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
 * 拓扑排序：依赖包排在前面
 */
function getUpdateOrder(packages) {
  const { graph, inDegree } = buildDependencyGraph(packages);
  const queue = Object.keys(inDegree)
    .filter((name) => inDegree[name] === 0)
    .sort();
  const order = [];

  while (queue.length > 0) {
    const current = queue.shift();
    order.push(current);

    const dependents = graph[current].slice().sort();
    for (const dependent of dependents) {
      inDegree[dependent]--;
      if (inDegree[dependent] === 0) {
        queue.push(dependent);
        queue.sort();
      }
    }
  }

  if (order.length !== Object.keys(packages).length) {
    // 存在循环依赖，回退到字母顺序
    return Object.keys(packages).sort();
  }

  return order;
}

/**
 * 判断包是否有需要升级的外部依赖
 */
function hasExternalDependencies(packageInfo) {
  const allDeps = {
    ...packageInfo.dependencies,
    ...packageInfo.devDependencies,
    ...packageInfo.peerDependencies,
  };

  return Object.values(allDeps).some(
    (version) => typeof version === 'string' && !version.startsWith('workspace:')
  );
}

/**
 * 统计可升级的依赖数量
 */
function countUpgradableDependencies(packageInfo) {
  const allDeps = {
    ...packageInfo.dependencies,
    ...packageInfo.devDependencies,
    ...packageInfo.peerDependencies,
  };

  return Object.values(allDeps).filter(
    (version) => typeof version === 'string' && !version.startsWith('workspace:')
  ).length;
}

/**
 * 升级单个包
 */
function updatePackage(packageName, packageInfo, options) {
  const workspaceDeps = getWorkspaceDependencies(packageInfo);
  const catalogDeps = getCatalogDependencies(packageInfo);
  const upgradableCount = countUpgradableDependencies(packageInfo);

  console.log(`\n📦 ${packageName}${packageInfo.isRoot ? ' (root)' : ''}`);
  console.log(`   可升级外部依赖: ${upgradableCount} 个`);
  if (workspaceDeps.length > 0) {
    console.log(`   workspace 依赖: ${workspaceDeps.length} 个 (跳过)`);
  }
  if (catalogDeps.length > 0) {
    console.log(`   catalog 依赖: ${catalogDeps.length} 个 (同步更新 catalog)`);
  }

  if (upgradableCount === 0) {
    console.log(`   ⏭️  无外部依赖，跳过`);
    return true;
  }

  if (options.dryRun) {
    const dryRunCommand = packageInfo.isRoot
      ? 'pnpm update --latest'
      : `pnpm --filter "${packageName}" update --latest`;
    console.log(`   📝 干跑模式: ${dryRunCommand}`);
    return true;
  }

  try {
    if (packageInfo.isRoot) {
      console.log(`   🚀 Running: pnpm update --latest`);
      execSync('pnpm update --latest', {
        stdio: 'inherit',
        cwd: ROOT_DIR,
      });
    } else {
      console.log(`   🚀 Running: pnpm --filter "${packageName}" update --latest`);
      execSync(`pnpm --filter "${packageName}" update --latest`, {
        stdio: 'inherit',
        cwd: ROOT_DIR,
      });
    }
    console.log(`   ✅ ${packageName} 升级完成`);
    return true;
  } catch (error) {
    console.error(`   ❌ ${packageName} 升级失败`);
    if (!options.continueOnError) {
      throw error;
    }
    return false;
  }
}

/**
 * 主函数
 */
function main() {
  const options = parseArgs(process.argv);

  console.log('🔍 扫描工作区 JS/TS 包...');

  try {
    const packages = getAllPackages();
    const packageNames = Object.keys(packages);

    if (packageNames.length === 0) {
      console.error('❌ 未找到任何包');
      process.exit(1);
    }

    // 如果指定了目标包，检查是否存在
    if (options.targetPackage && !packages[options.targetPackage]) {
      console.error(`\n❌ 未找到包: ${options.targetPackage}`);
      console.error('\n可用的包:');
      for (const pkgName of packageNames.sort()) {
        console.error(`  - ${pkgName}`);
      }
      process.exit(1);
    }

    // 计算更新顺序
    const updateOrder = options.targetPackage
      ? [options.targetPackage]
      : getUpdateOrder(packages);

    console.log(`\n📋 发现 ${updateOrder.length} 个待处理包:`);
    updateOrder.forEach((pkg, index) => {
      const marker = pkg === options.targetPackage ? '🎯' : '  ';
      const depCount = countUpgradableDependencies(packages[pkg]);
      console.log(`${marker} ${index + 1}. ${pkg} (${depCount} 个可升级依赖)`);
    });

    if (options.dryRun) {
      console.log('\n📝 干跑模式：仅预览，不执行实际升级');
    }

    // 按顺序升级
    console.log(`\n🚀 开始升级依赖...\n`);
    let successCount = 0;
    let skipCount = 0;
    let failCount = 0;

    for (const pkgName of updateOrder) {
      const pkgInfo = packages[pkgName];
      const upgradableCount = countUpgradableDependencies(pkgInfo);

      const success = updatePackage(pkgName, pkgInfo, options);
      if (success) {
        if (upgradableCount === 0) {
          skipCount++;
        } else {
          successCount++;
        }
      } else {
        failCount++;
      }
    }

    console.log('\n📊 升级总结:');
    console.log(`   成功: ${successCount} 个包`);
    console.log(`   跳过: ${skipCount} 个包 (无外部依赖)`);
    if (failCount > 0) {
      console.log(`   失败: ${failCount} 个包`);
    }

    if (failCount > 0) {
      process.exit(1);
    }

    if (options.dryRun) {
      console.log('\n✨ 干跑完成。去掉 --dry-run 参数以执行实际升级。');
    } else {
      console.log('\n✨ 所有依赖升级完成！');
    }
  } catch (error) {
    console.error('\n❌ 升级失败:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  getAllPackages,
  getUpdateOrder,
  updatePackage,
};
