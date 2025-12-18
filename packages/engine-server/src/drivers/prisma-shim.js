import fs from "fs";
import path from "path";
import os from "os";
import https from "https";
import { createRequire } from "module";

// adm-zip.js is a CommonJS module, so we need to use createRequire
const require = createRequire(import.meta.url);
const { admZip: AdmZip } = require("./adm-zip.js");

const DENDRON_SYSTEM_ROOT = path.join(os.homedir(), ".dendron");

async function downloadPrisma() {

  return new Promise((resolve, reject) => {
    const url = "https://d2q204iup008xl.cloudfront.net/publish/generated-prisma-client.zip";
    const tmpPath = path.join(DENDRON_SYSTEM_ROOT, "tmp_client");
    if (fs.existsSync(tmpPath)) {
      fs.unlinkSync(tmpPath);
    }
    const file = fs.createWriteStream(tmpPath);
    https.get(url, (response) => {
      response.pipe(file);

      // after download completed close filestream
      file.on("finish", () => {
        file.close();
        resolve({ prismaDownloadPath: tmpPath });
      });
      file.on("error", (err) => {
        reject(err)
      })
    });

  })
}

async function loadPrisma() {
  const prismaPath = path.join(DENDRON_SYSTEM_ROOT, "generated-prisma-client");
  // Convert path to file:// URL for dynamic import (works cross-platform)
  const prismaModulePath = path.join(prismaPath, "index.js");
  
  if (fs.existsSync(prismaPath)) {
    // Dynamic import for ESM - use file:// URL for cross-platform compatibility
    const prismaUrl = `file://${prismaModulePath}`;
    const prismaModule = await import(prismaUrl);
    return {
      Prisma: prismaModule.Prisma,
      PrismaClient: prismaModule.PrismaClient,
    };
  } else {
    const { prismaDownloadPath } = await downloadPrisma();

    // Prisma not installed
    const zip = new AdmZip(prismaDownloadPath);
    zip.extractAllTo(prismaPath, true);
    // TODO: remove download
    const prismaUrl = `file://${prismaModulePath}`;
    const prismaModule = await import(prismaUrl);
    return {
      Prisma: prismaModule.Prisma,
      PrismaClient: prismaModule.PrismaClient,
    };
  }
}

export { loadPrisma };
