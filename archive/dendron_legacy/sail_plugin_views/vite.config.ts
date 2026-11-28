import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { nodePolyfills } from 'vite-plugin-node-polyfills';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    nodePolyfills({
      // Only include necessary polyfills
      include: ['events', 'buffer', 'util', 'stream', 'path'],
      // Don't use shims for process - define it globally instead
      globals: {
        process: false,  // Disable process shim
        Buffer: true,
      },
    }),
  ],
  define: {
    // Define process globally to avoid shim issues
    'process.env': {},
    'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'development'),
    'process.browser': true,
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js'],
  },
  // Optimize dependencies to handle CommonJS/ESM compatibility
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'react-redux',
      '@reduxjs/toolkit',
      'redux-logger',
      'lodash',
      'dayjs',
      'mermaid',
      '@saili/common-all',
    ],
    // Exclude server-only packages that have Node.js dependencies
    exclude: ['@saili/common-server'],
    // Force re-optimization when workspace dependencies change
    force: true,
    rolldownOptions: {
      // keepNames is esbuild-specific; Vite 8 uses Rolldown for dep optimization.
      // Retain original intent only if the option is supported; otherwise leave empty.
    },
  },
  server: {
    port: 4000,
    open: true,
    strictPort: false,
  },
  build: {
    outDir: 'build',
    sourcemap: true,
    // Keep the default chunk size warning threshold; manualChunks below keeps all
    // emitted chunks under this limit.
    chunkSizeWarningLimit: 1000,
    // Ensure CSS is extracted to a single file
    cssCodeSplit: false,
    rollupOptions: {
      onwarn(warning, warn) {
        // Suppress eval warning from gray-matter's engine.js
        if (warning.code === 'EVAL' && warning.id?.includes('gray-matter')) {
          return;
        }
        warn(warning);
      },
      output: {
        // Fixed output names for vscode_plugin integration
        entryFileNames: 'static/js/index.bundle.js',
        chunkFileNames: 'static/js/[name]-[hash].js',
        // Split heavy dependencies into separate chunks so the entry bundle stays
        // below the 1000 kB warning threshold. The VSCode webview entry still only
        // needs to load index.bundle.js; the runtime will dynamically fetch the
        // split chunks relative to the entry script URL.
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('@aws-amplify')) {
              return 'vendor-amplify';
            }
            return 'vendor';
          }
        },
        // Use fixed CSS name: index.styles.css (required by vscode_plugin)
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.endsWith('.css')) {
            return 'static/css/index.styles.css';
          }
          return 'static/[ext]/[name]-[hash][extname]';
        },
      },
    },
  },
  publicDir: 'public',
  base: './',  // Use relative paths for VSCode webview compatibility
});
