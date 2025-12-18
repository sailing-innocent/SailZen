#!/usr/bin/env node
/**
 * Prisma Client Build Script
 * 
 * This script handles the Prisma client generation and file copying
 * for the monorepo build process.
 */

import fs from "fs-extra";
import path from "path";
import os from "os";

const DENDRON_SYSTEM_ROOT = path.join(os.homedir(), ".dendron");

interface BuildOptions {
  /** Source directory for generated Prisma client */
  srcPath: string;
  /** Target directory for runtime Prisma client */
  runtimePath: string;
  /** Source directory for shim files */
  shimSrcPath: string;
  /** Target directory for shim files in lib */
  shimLibPath: string;
  /** List of additional files to copy */
  additionalFiles: string[];
}

class PrismaBuilder {
  private options: BuildOptions;

  constructor(options: BuildOptions) {
    this.options = options;
  }

  /**
   * Ensures a directory exists, creating it if necessary
   */
  private ensureDir(dirPath: string): void {
    fs.ensureDirSync(dirPath);
  }

  /**
   * Copies a file or directory from source to destination
   */
  private async copyItem(src: string, dest: string): Promise<void> {
    try {
      const stat = await fs.stat(src);
      if (stat.isDirectory()) {
        await fs.copy(src, dest, { overwrite: true });
      } else {
        await fs.copy(src, dest, { overwrite: true });
      }
    } catch (error) {
      throw new Error(`Failed to copy ${src} to ${dest}: ${error}`);
    }
  }

  /**
   * Validates that required source paths exist
   */
  private validateSources(): void {
    const { srcPath, shimSrcPath, additionalFiles } = this.options;

    if (!fs.existsSync(srcPath)) {
      throw new Error(
        `Prisma client not found at ${srcPath}. Run 'pnpm prisma generate' first.`
      );
    }

    if (!fs.existsSync(shimSrcPath)) {
      throw new Error(`Shim file not found at ${shimSrcPath}`);
    }

    for (const file of additionalFiles) {
      const filePath = path.join(path.dirname(shimSrcPath), file);
      if (!fs.existsSync(filePath)) {
        throw new Error(`Additional file not found: ${filePath}`);
      }
    }
  }

  /**
   * Copies Prisma client to runtime location
   */
  private async copyPrismaClient(): Promise<void> {
    const { srcPath, runtimePath } = this.options;
    console.log(`Copying Prisma client from ${srcPath} to ${runtimePath}`);
    this.ensureDir(DENDRON_SYSTEM_ROOT);
    await this.copyItem(srcPath, runtimePath);
    console.log("✓ Prisma client copied successfully");
  }

  /**
   * Copies shim and additional files to lib directory
   */
  private async copyShimFiles(): Promise<void> {
    const { shimSrcPath, shimLibPath, additionalFiles } = this.options;

    // Copy shim file
    console.log(`Copying shim file to ${shimLibPath}`);
    this.ensureDir(path.dirname(shimLibPath));
    await this.copyItem(shimSrcPath, shimLibPath);
    console.log("✓ Shim file copied successfully");

    // Copy additional files
    for (const file of additionalFiles) {
      const srcFile = path.join(path.dirname(shimSrcPath), file);
      const destFile = path.join(path.dirname(shimLibPath), file);
      console.log(`Copying ${file} to lib`);
      await this.copyItem(srcFile, destFile);
      console.log(`✓ ${file} copied successfully`);
    }
  }

  /**
   * Main build method
   */
  async build(): Promise<void> {
    console.log("Starting Prisma build process...");
    
    try {
      this.validateSources();
      await this.copyPrismaClient();
      await this.copyShimFiles();
      console.log("✓ Prisma build completed successfully");
    } catch (error) {
      console.error("✗ Prisma build failed:", error);
      process.exit(1);
    }
  }
}

/**
 * Get the directory name of the current module (ESM compatible)
 */
function getDirname(): string {
  // In ESM, we can use import.meta.url
  if (typeof import.meta !== "undefined" && import.meta.url) {
    const url = new URL(import.meta.url);
    // Handle file:// URLs correctly on Windows
    let filePath = url.pathname;
    if (process.platform === "win32" && filePath.startsWith("/")) {
      filePath = filePath.slice(1);
    }
    return path.dirname(filePath);
  }
  // Fallback: use process.argv[1]
  return path.dirname(process.argv[1]);
}

/**
 * Main execution
 */
async function main() {
  // Get project root by resolving from scripts directory
  const scriptDir = getDirname();
  const projectRoot = path.resolve(scriptDir, "..");
  const srcDir = path.join(projectRoot, "src", "drivers");
  const libDir = path.join(projectRoot, "lib", "drivers");

  const builder = new PrismaBuilder({
    srcPath: path.join(srcDir, "generated-prisma-client"),
    runtimePath: path.join(DENDRON_SYSTEM_ROOT, "generated-prisma-client"),
    shimSrcPath: path.join(srcDir, "prisma-shim.js"),
    shimLibPath: path.join(libDir, "prisma-shim.js"),
    additionalFiles: ["adm-zip.js"],
  });

  await builder.build();
}

// Run main if this file is executed directly (ESM compatible)
// Check if this is the main module by comparing import.meta.url with the script path
const isMainModule = import.meta.url === `file://${path.resolve(process.argv[1])}` || 
                     process.argv[1]?.includes("build-prisma");

if (isMainModule) {
  main().catch((error) => {
    console.error("Unhandled error:", error);
    process.exit(1);
  });
}

export { PrismaBuilder };
