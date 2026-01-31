# Development Overview

## Prepare Environment

Installation

```bash
# Install all dependencies
pnpm install
# Install plugin dependencies only
pnpm install-plugin
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

#### Known Issues

See [KNOWN_ISSUES.md](./KNOWN_ISSUES.md) for documented issues and workarounds.