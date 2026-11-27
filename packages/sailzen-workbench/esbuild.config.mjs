import * as esbuild from "esbuild";

const isWatch = process.argv.includes("--watch");
const isProd = process.argv.includes("--production");

/** @type {import('esbuild').BuildOptions} */
const buildOptions = {
  entryPoints: ["src/extension.ts"],
  bundle: true,
  outfile: "dist/extension.js",
  platform: "node",
  target: "node18",
  format: "cjs",
  external: ["vscode"],
  sourcemap: !isProd,
  minify: isProd,
  logLevel: "info",
};

if (isWatch) {
  const ctx = await esbuild.context(buildOptions);
  await ctx.watch();
  console.log("[sailzen-workbench] watching for changes...");
} else {
  await esbuild.build(buildOptions);
}
