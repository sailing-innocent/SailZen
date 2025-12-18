# Prisma Build Scripts

## Overview

This directory contains build scripts for managing Prisma client generation and deployment in the monorepo.

## Scripts

### `build-prisma.ts`

TypeScript-based build script that handles:
- Prisma client generation validation
- Copying generated Prisma client to runtime location (`~/.dendron/generated-prisma-client`)
- Copying shim files (`prisma-shim.js`, `adm-zip.js`) to the compiled `lib` directory

## Usage

The script is automatically executed as part of the build process:

```bash
# Generate Prisma client and run post-install steps
pnpm buildPrismaClient

# Or run steps separately
pnpm prisma:generate      # Generate Prisma client
pnpm prisma:postinstall   # Copy files to appropriate locations
```

## Build Flow

1. **Prisma Generation**: `prisma generate` creates the client in `src/drivers/generated-prisma-client`
2. **Post-install**: The build script copies:
   - Prisma client → `~/.dendron/generated-prisma-client` (runtime location)
   - Shim files → `lib/drivers/` (compiled output)

## Architecture

The script uses a class-based approach (`PrismaBuilder`) for better maintainability:
- **Validation**: Ensures all required files exist before copying
- **Error Handling**: Provides clear error messages for debugging
- **Type Safety**: Written in TypeScript for better IDE support

## Migration from `copyPrismaClient.js`

The old JavaScript-based script has been replaced with this TypeScript version for:
- Better type safety
- Improved error messages
- Easier maintenance
- Better integration with the monorepo build system
