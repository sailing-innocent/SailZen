# @saili/Dendron Plugin Views

The Frontend UI for Dendron Plugin (VSCode Webview)

- React + Vite → JS/CSS bundle → embedded into HTML → VSCode webview

## Project Structure

```
dendron_plugin_views/
├── src/
│   ├── components/       # React components (DendronNotePreview, DendronCalendarPanel, etc.)
│   ├── features/         # Redux slices (engine, ide)
│   ├── hooks/            # Custom React hooks
│   ├── mock/             # Mock data for standalone development
│   ├── utils/            # Utility functions
│   ├── index.tsx         # Production entry point
│   └── dev.tsx           # Development entry point with mock data
├── index.html            # Production HTML template
├── dev.html              # Development HTML template with toolbar
├── scripts/
│   └── copyToPlugin.js   # Script to copy build to vscode_plugin
└── vite.config.ts        # Vite configuration
```

## Development Workflow

### 1. Standalone Component Development (Recommended for UI work)

For developing and testing component styles without VSCode and backend API:

```bash
# From project root
pnpm views:dev

# Or from this directory
pnpm dev
```

This opens a browser with:
- **Mock data** - No backend required
- **Dev toolbar** - Switch components and themes
- **Hot reload** - Fast iteration on styles

### 2. Integrated Development (With VSCode Extension)

For testing with the real VSCode extension:

```bash
# From project root - builds views, copies to plugin, starts watch mode
pnpm plugin:dev
```

### 3. Production Build

```bash
# Build views only
pnpm views:build

# Build and package complete plugin
pnpm plugin:package
```

## Build Output

The build produces:
- `build/static/js/index.bundle.js` - JavaScript bundle
- `build/static/css/index.styles.css` - CSS styles

These are copied to `packages/vscode_plugin/assets/` (dev) and `packages/vscode_plugin/dist/` (prod).

## Adding New Components

1. Create component in `src/components/YourComponent.tsx`
2. Add to `VALID_NAMES` in `src/index.tsx` and `src/dev.tsx`
3. Add mock data in `src/mock/mockData.ts` if needed
4. Test with `pnpm dev`

## Available Components

- `DendronNotePreview` - Note preview panel
- `DendronCalendarPanel` - Calendar view for daily notes

## Mock Mode

The `data-mock="true"` attribute on the root element enables mock mode:
- No API calls to backend
- Uses predefined mock data
- Simulates VSCode theme variables

## Legacy Notes

Previously used webpack, now migrated to Vite for faster development.
