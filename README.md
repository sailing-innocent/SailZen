# SailZen

## Maintain Script

- only build site `pnpm install-site`
- run build site `pnpm run build-site`
- run server `python server.py`

## vscode-plugin

`pnpm install`

The plugin uses `better-sqlite3` for local database management. This is a native module that needs to be compiled for your platform.

debugging: press `F5` in vscode, will automatically compile and watch

build

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
