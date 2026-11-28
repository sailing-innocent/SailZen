/**
 * @file compileService.ts
 * @brief Document compilation service for SailZen Doc Engine
 * @description Integrates with external build toolchains (xmake, latexmk,
 *   typst-cli) to compile generated documents. Supports shadow output dirs
 *   under .sailzen/doc/.
 */

import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";
import { GeneratedDocument, DocExportConfig } from "@saili/common-all";

export type CompileEngine = "latexmk" | "xmake" | "typst" | "slidev";

export type CompileResult = {
  success: boolean;
  outputPath?: string;
  logPath?: string;
  message: string;
};

// ============================================================================
// Public API
// ============================================================================

/**
 * Write a generated document to disk in the shadow output directory,
 * then compile it with the appropriate engine.
 */
export async function compileDocument(
  generated: GeneratedDocument,
  exportConfig: DocExportConfig,
  wsRoot: string,
  projectName: string,
  engine?: CompileEngine
): Promise<CompileResult> {
  const outDir = resolveOutputDir(wsRoot, projectName, exportConfig);
  await ensureDir(outDir);

  // Write main file
  const mainFileName = `main.${generated.ext}`;
  const mainPath = path.join(outDir, mainFileName);
  fs.writeFileSync(mainPath, generated.mainContent, "utf-8");

  // Write extra files
  for (const ef of generated.extraFiles || []) {
    const efPath = path.join(outDir, ef.path);
    await ensureDir(path.dirname(efPath));
    fs.writeFileSync(efPath, ef.content, "utf-8");
  }

  // Write/asset copy figures
  const figuresDir = path.join(outDir, "figures");
  await ensureDir(figuresDir);
  for (const af of generated.assetFiles || []) {
    const dest = path.join(outDir, af.destPath);
    await ensureDir(path.dirname(dest));
    try {
      fs.copyFileSync(af.srcPath, dest);
    } catch {
      // If copy fails (e.g., source missing), leave a placeholder
    }
  }

  // Copy template dependency files
  for (const tf of generated.templateFiles || []) {
    const dest = path.join(outDir, tf.destPath);
    await ensureDir(path.dirname(dest));
    try {
      fs.copyFileSync(tf.srcPath, dest);
    } catch {
      // Ignore missing template assets
    }
  }

  // Write split sections
  if (generated.sections && generated.sections.length > 0) {
    const sectionsDir = path.join(outDir, "sections");
    await ensureDir(sectionsDir);
    for (const sec of generated.sections) {
      fs.writeFileSync(
        path.join(sectionsDir, sec.fileName),
        sec.content,
        "utf-8"
      );
    }
  }

  // Determine engine
  const detectedEngine =
    engine || detectEngine(exportConfig, generated.meta.engine);

  // Compile
  switch (detectedEngine) {
    case "latexmk":
      return runLatexmk(outDir, mainFileName, wsRoot);
    case "xmake":
      return runXmake(outDir, wsRoot, projectName);
    case "typst":
      return runTypst(outDir, mainFileName, wsRoot);
    default:
      return {
        success: true,
        outputPath: outDir,
        message: `Output written to ${outDir}. No compilation engine configured for ${detectedEngine}.`,
      };
  }
}

// ============================================================================
// Output directory resolution
// ============================================================================

function resolveOutputDir(
  wsRoot: string,
  projectName: string,
  exportConfig: DocExportConfig
): string {
  const format = exportConfig.format || "latex";
  const template = exportConfig.template || "default";
  if (exportConfig.outDir) {
    return path.isAbsolute(exportConfig.outDir)
      ? exportConfig.outDir
      : path.join(wsRoot, exportConfig.outDir);
  }
  return path.join(
    wsRoot,
    ".sailzen",
    "doc",
    projectName,
    `${format}-${template}`
  );
}

async function ensureDir(dir: string): Promise<void> {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function detectEngine(
  exportConfig: DocExportConfig,
  metaEngine?: string
): CompileEngine {
  const format = exportConfig.format;
  if (format === "typst") return "typst";
  if (format === "slidev") return "slidev";
  // Prefer xmake if available, else latexmk
  return metaEngine === "xmake" ? "xmake" : "latexmk";
}

// ============================================================================
// latexmk runner
// ============================================================================

async function runLatexmk(
  outDir: string,
  mainFile: string,
  _wsRoot: string
): Promise<CompileResult> {
  const terminal = vscode.window.createTerminal({
    name: "SailZen LaTeX",
    cwd: outDir,
  });

  const hasLatexmkrc = fs.existsSync(path.join(outDir, "latexmkrc"));
  const args = hasLatexmkrc
    ? ["-pdf", "-silent", mainFile]
    : ["-pdf", "-xelatex", "-shell-escape", "-silent", mainFile];

  terminal.sendText(`latexmk ${args.join(" ")}`);
  terminal.show();

  return {
    success: true,
    outputPath: path.join(outDir, mainFile.replace(/\.tex$/, ".pdf")),
    message: `latexmk started in ${outDir}. Check the terminal for progress.`,
  };
}

// ============================================================================
// xmake runner
// ============================================================================

async function runXmake(
  outDir: string,
  wsRoot: string,
  projectName: string
): Promise<CompileResult> {
  // Check if there's an xmake.lua in the doc directory
  const docXmakeLua = path.join(wsRoot, "doc", "xmake.lua");
  const hasDocXmake = fs.existsSync(docXmakeLua);

  const terminal = vscode.window.createTerminal({
    name: "SailZen xmake",
    cwd: hasDocXmake ? path.join(wsRoot, "doc") : outDir,
  });

  if (hasDocXmake) {
    // Use the existing SailDoc xmake build system
    // Create a minimal xmake.lua in the output dir that includes the main doc xmake
    const includeLua = `includes("${path.relative(outDir, wsRoot).replace(/\\/g, "/")}/doc/xmake.lua")\n`;
    const localXmake = path.join(outDir, "xmake.lua");
    if (!fs.existsSync(localXmake)) {
      fs.writeFileSync(localXmake, includeLua, "utf-8");
    }
    terminal.sendText(`xmake -P "${outDir}"`);
  } else {
    terminal.sendText(`xmake -P "${outDir}"`);
  }

  terminal.show();

  return {
    success: true,
    outputPath: path.join(outDir, "build", "main.pdf"),
    message: `xmake started in ${outDir}. Check the terminal for progress.`,
  };
}

// ============================================================================
// typst runner
// ============================================================================

async function runTypst(
  outDir: string,
  mainFile: string,
  _wsRoot: string
): Promise<CompileResult> {
  const terminal = vscode.window.createTerminal({
    name: "SailZen Typst",
    cwd: outDir,
  });

  const outputPdf = mainFile.replace(/\.typ$/, ".pdf");
  terminal.sendText(`typst compile "${mainFile}" "${outputPdf}"`);
  terminal.show();

  return {
    success: true,
    outputPath: path.join(outDir, outputPdf),
    message: `typst compile started in ${outDir}. Check the terminal for progress.`,
  };
}
