import type { StorybookConfig } from "@storybook/react-vite";
import path from "node:path";

const config: StorybookConfig = {
  stories: [
    "../src/**/*.mdx",
    "../src/**/*.stories.@(js|jsx|ts|tsx)",
  ],
  addons: ["@storybook/addon-a11y", "@storybook/addon-themes"],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  docs: {},
  viteFinal: async (config) => {
    // Ensure path alias for "@"
    const baseFind = "@";
    const baseReplacement = path.resolve(__dirname, "../src");
    const ensureAlias = (cfg: any) => {
      cfg.resolve = cfg.resolve || {};
      const current = cfg.resolve.alias;
      if (Array.isArray(current)) {
        if (!current.find((a: any) => a?.find === baseFind)) {
          current.push({ find: baseFind, replacement: baseReplacement });
        }
        cfg.resolve.alias = current;
      } else if (current && typeof current === "object") {
        if (!current[baseFind]) current[baseFind] = baseReplacement;
        cfg.resolve.alias = current;
      } else {
        cfg.resolve.alias = [{ find: baseFind, replacement: baseReplacement }];
      }
    };
    ensureAlias(config);
    // Dynamically import Tailwind's Vite plugin (optional).
    try {
      const mod = await import("@tailwindcss/vite");
      const tailwindPlugin = (mod as any).default ?? (mod as any);
      const plugins: any[] = Array.isArray((config as any).plugins)
        ? ((config as any).plugins as any[])
        : [];
      const hasTailwind = plugins.some((p: any) => (p?.name ?? "").includes("@tailwindcss/vite"));
      if (!hasTailwind) plugins.push(tailwindPlugin());
      (config as any).plugins = plugins;
    } catch {
      // If plugin not available, continue without it.
    }
    return config;
  },
};

export default config;
