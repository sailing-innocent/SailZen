# SailZen

A personal knowledge management and productivity tool based on VSCode extension.

## Quick Start

### Prerequisites

- Node.js 18+
- pnpm 8+
- Python 3.10+ (for backend server)

### Installation

```bash
# Install all dependencies
pnpm install

# Install plugin dependencies only
pnpm install-plugin
```

## Development

### VSCode Plugin Development

```bash
# Start development mode (watches for changes)
pnpm plugin:dev

# Or press F5 in VSCode to launch debug mode
```

### Build & Package

### Running Tests

```bash
# Run all tests
pnpm test

# Run specific package tests
pnpm test:common-all
pnpm test:common-server
pnpm test:unified

# Run tests with coverage
pnpm test:coverage
```

## Maintenance

### Version Management

All packages in the monorepo share the same version number. Use the bump-version script to update versions:

```bash
# Show current version and usage
node scripts/bump-version.js

# Set specific version
node scripts/bump-version.js 0.2.0

# Bump patch version (0.1.0 → 0.1.1)
node scripts/bump-version.js patch

# Bump minor version (0.1.0 → 0.2.0)
node scripts/bump-version.js minor

# Bump major version (0.1.0 → 1.0.0)
node scripts/bump-version.js major
```

### Release Workflow

1. **Update Version**
   ```bash
   node scripts/bump-version.js <new-version>
   ```

2. **Build & Test**
   ```bash
   pnpm plugin:build
   pnpm test
   ```

3. **Package VSIX**
   ```bash
   pnpm plugin:package
   ```

4. **Verify Package**
   - Install the VSIX in a fresh VSCode instance
   - Test Calendar View and Tree View functionality
   - Verify journal note creation and navigation

5. **Commit & Tag**
   ```bash
   git add -A
   git commit -m "chore: release v<version>"
   git tag v<version>
   git push && git push --tags
   ```

### Project Structure

```
SailZen/
├── packages/
│   ├── vscode_plugin/      # Main VSCode extension
│   ├── dendron_plugin_views/  # React UI components (Calendar, TreeView)
│   ├── common-all/         # Shared types and utilities
│   ├── common-server/      # Server-side utilities
│   ├── engine-server/      # Note engine and database
│   ├── unified/            # Markdown processing
│   ├── api_server/         # API server
│   └── site/               # Documentation site
├── sail_server/            # Python backend server
├── scripts/
│   └── bump-version.js     # Version management script
└── assets/                 # Test workspace and assets
```



### Key Build Commands

依赖构建
# 直接使用脚本
node scripts/build-with-deps.js @saili/engine-server
node scripts/build-with-deps.js @saili/engine-server buildCI
node scripts/build-with-deps.js sail-zen-vscode build

# 使用 package.json 中的命令
pnpm build-engine-server
pnpm build-plugin
pnpm build:common-server


| Command               | Description                       |
| --------------------- | --------------------------------- |
| `pnpm install`        | Install all dependencies          |
| `pnpm plugin:dev`     | Start development mode with watch |
| `pnpm plugin:build`   | Full production build             |
| `pnpm plugin:package` | Create VSIX package               |
| `pnpm views:build`    | Build React UI components only    |
| `pnpm views:copy`     | Copy UI assets to plugin          |
| `pnpm test`           | Run all tests                     |

### Troubleshooting

#### Native Module Issues (better-sqlite3)

The plugin uses `better-sqlite3` which requires native compilation:

**Windows:**
```bash
npm install --global windows-build-tools
```

**macOS:**
```bash
xcode-select --install
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install build-essential python3
```

#### Calendar View Not Showing in VSIX

Ensure the `assets/` directory is included in the package:
- Check `.vscodeignore` does NOT exclude `assets`
- Run `pnpm views:build && pnpm views:copy` before packaging

#### Known Issues

See [doc/KNOWN_ISSUES.md](doc/KNOWN_ISSUES.md) for documented issues and workarounds.

## Backend Server (Python)

```bash
# Install Python dependencies
uv sync

# Run server
python server.py
```

## License

MIT
