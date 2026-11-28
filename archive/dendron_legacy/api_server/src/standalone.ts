// -*- coding: utf-8 -*-
// @file standalone.ts
// @brief Vault API Server 独立启动入口 - 不依赖 VSCode 插件，可单独运行
// @author sailing-innocent
// @date 2026-05-06
// @version 1.0
// ---------------------------------
//
// 用法:
//   # 开发模式 (tsx, 无需构建)
//   WS_ROOT=/path/to/vault npx tsx src/standalone.ts
//
//   # 生产模式 (先构建)
//   pnpm build
//   WS_ROOT=/path/to/vault node lib/standalone.js
//
//   # Windows PowerShell
//   $env:WS_ROOT="D:/my-vault"; $env:PORT=3005; npx tsx src/standalone.ts

import process from "process";
import { launchv2 } from "./index.js";
import { WorkspaceController } from "./modules/workspace/index.js";

// ============================================================================
// 读取环境变量
// ============================================================================

const port = Number(process.env.PORT ?? 3005);
const wsRoot = process.env.WS_ROOT;
const logPath = process.env.LOG_DST ?? "stdout";

// ============================================================================
// 参数校验
// ============================================================================

if (!wsRoot) {
  console.error("❌ 必须指定 WS_ROOT 环境变量 (vault 根目录)");
  console.error("");
  console.error("用法:");
  console.error("  WS_ROOT=/path/to/vault npx tsx src/standalone.ts");
  console.error("  WS_ROOT=/path/to/vault PORT=3005 node lib/standalone.js");
  console.error("");
  console.error("Windows PowerShell:");
  console.error(
    '  $env:WS_ROOT="D:/my-vault"; $env:PORT=3005; npx tsx src/standalone.ts'
  );
  process.exit(1);
}

// ============================================================================
// 启动服务器
// ============================================================================

console.log("🚀 Vault API Server 启动中...");
console.log(`   vault : ${wsRoot}`);
console.log(`   port  : ${port}`);
console.log("");

// 1. 启动 Express HTTP 服务器
const { port: actualPort } = await launchv2({ port, logPath });
console.log(`✅ HTTP 服务器已就绪: http://localhost:${actualPort}`);

// 2. 自动初始化工作区（替代 VSCode 插件手动触发 /api/workspace/initialize）
console.log(`📂 正在加载 vault: ${wsRoot}`);
const initResult = await WorkspaceController.instance().init({ uri: wsRoot });

if (initResult.error && (initResult.error as any).severity === "FATAL") {
  console.error("❌ Vault 初始化失败:", initResult.error);
  process.exit(1);
}

const noteCount = Object.keys(initResult.data?.notes ?? {}).length;
const vaultCount = initResult.data?.vaults?.length ?? 0;

console.log(`✅ Vault 初始化完成`);
console.log(`   笔记数 : ${noteCount}`);
console.log(`   Vault 数: ${vaultCount}`);

if (initResult.error) {
  console.warn(`⚠️  初始化有警告:`, initResult.error);
}

// ============================================================================
// 打印 API 说明
// ============================================================================

const base = `http://localhost:${actualPort}`;
const ws = encodeURIComponent(wsRoot);

console.log("");
console.log("📖 可用 API:");
console.log(`  GET  ${base}/api/note/query?ws=${ws}&q=*`);
console.log(`  GET  ${base}/api/note/get?ws=${ws}&id=<note-id>`);
console.log(`  POST ${base}/api/note/write          body: {ws, node, opts?}`);
console.log(`  POST ${base}/api/note/find           body: {ws, fname?, vault?}`);
console.log(`  POST ${base}/api/note/delete         body: {ws, id}`);
console.log(`  POST ${base}/api/note/rename         body: {ws, loc, newLoc}`);
console.log(`  GET  ${base}/api/note/blocks?ws=${ws}&id=<note-id>`);
console.log(`  POST ${base}/api/workspace/initialize  body: {uri}`);
console.log("");
console.log("🔧 环境变量:");
console.log(`  WS_ROOT  : vault 根目录路径 (必须)`);
console.log(`  PORT     : 监听端口 (默认: 3005)`);
console.log(`  LOG_DST  : 日志输出路径 (默认: stdout)`);
console.log("");
console.log("Ctrl+C 停止服务器");

// ============================================================================
// 优雅退出
// ============================================================================

process.on("SIGINT", () => {
  console.log("\n👋 服务器已停止");
  process.exit(0);
});
