# SailZen Project Guide for AI Agents

## Project Overview

SailZen is a personal knowledge management and productivity tool based on VSCode extension. It consists of a TypeScript/JavaScript monorepo for the frontend/extension and a Python backend for data management and API services.

The project is based on Dendron (a hierarchical note-taking tool) and extends it with personal finance tracking, health monitoring, project management, text analysis, and necessity/inventory management.

## Technology Stack

### Frontend / Extension (TypeScript/JavaScript)
- **Package Manager**: pnpm with workspace configuration
- **Build Tool**: TypeScript compiler + esbuild for VSCode extension
- **UI Framework**: React 19 + Tailwind CSS 4 + Radix UI components
- **State Management**: Zustand (site), Redux Toolkit (plugin views)
- **Testing**: Jest with ts-jest
- **Charts**: Recharts
- **VSCode Extension API**: Targeting VSCode ^1.107.0

### Backend (Python)
- **Runtime**: Python >= 3.13
- **Package Manager**: uv (with workspace support)
- **Web Framework**: Litestar (ASGI) with uvicorn
- **Database**: PostgreSQL with SQLAlchemy 2.0 + psycopg
- **Data Serialization**: msgspec, pydantic
- **LLM Integration**: google-genai, openai
- **Scientific Computing**: numpy, scipy, scikit-learn, matplotlib
- **Testing**: pytest

## Project Structure

```
SailZen/
├── packages/                    # TypeScript monorepo packages
│   ├── common-all/             # Shared types, utilities, constants
│   ├── common-server/          # Server-side utilities
│   ├── unified/                # Markdown/unified parser utilities
│   ├── engine-server/          # Dendron engine with Prisma
│   ├── api_server/             # Express API server
│   ├── vscode_plugin/          # VSCode extension (main plugin)
│   ├── dendron_plugin_views/   # React webviews for plugin
│   └── site/                   # React web frontend (Vite)
├── sail_server/                # Python backend
│   ├── router/                 # Litestar API routers
│   ├── controller/             # Business logic controllers
│   ├── model/                  # SQLAlchemy models
│   ├── data/                   # Data access layer
│   ├── utils/                  # Utilities (LLM, time, etc.)
│   └── cli/                    # CLI commands
├── tests/                      # Python tests
│   ├── llm_integration/        # LLM integration tests
│   └── server/                 # Server API tests
├── scripts/                    # Build and utility scripts
└── doc/                        # Documentation
```

## Package Dependencies (Build Order)

The packages must be built in this dependency order:

1. `@saili/common-all` - Base types and utilities (no internal deps)
2. `@saili/common-server` - Depends on `common-all`
3. `@saili/unified` - Depends on `common-all`
4. `@saili/engine-server` - Depends on `common-all`, `common-server`, `unified`
5. `@saili/api-server` - Depends on `common-all`, `common-server`, `engine-server`, `unified`
6. `@saili/dendron-plugin-views` - Depends on `common-all`
7. `sail-zen-vscode` - Depends on all above
8. `sail-site` - Web frontend, depends on API

## Build Commands

### TypeScript Packages

```bash
# Build a specific package with all its dependencies
pnpm run build-with-deps @saili/engine-server

# Build all common packages
pnpm run build:common-all
pnpm run build:common-server
pnpm run build:unified

# Build VSCode plugin
pnpm run build-plugin

# Build and package the extension
pnpm run package-plugin

# Build web site
pnpm run build-site
```

### Python Backend

```bash
# Install dependencies
uv sync

# Run the main server
uv run server.py

# Run in development mode
uv run server.py --dev

# Run task dispatcher
uv run main.py --task <task_name> --args <args>

# Import text file
uv run main.py --import-text <file.txt> --title "Title" --author "Author" --prod
```

## Testing Commands

### TypeScript Tests

```bash
# Run all tests
pnpm test

# Run specific package tests
pnpm run test:common-all
pnpm run test:common-server
pnpm run test:unified

# Run with coverage
pnpm run test:coverage
```

### Python Tests

```bash
# Run all tests
uv run pytest

# Run with specific markers
uv run pytest -m "not asyncio"  # Skip async tests

# Run LLM integration tests
uv run tests/llm_integration/run_validation.py connection --real-connection --providers google
```

## Development Environment Setup

### Prerequisites
- Node.js >= 18.0.0
- Python >= 3.13
- pnpm (for TypeScript packages)
- uv (for Python packages)
- PostgreSQL database

### Environment Configuration

Create environment files based on `.env.template`:
- `.env.dev` - Development environment
- `.env.prod` - Production environment
- `.env.debug` - Debug environment

Required environment variables:
```bash
SERVER_PORT=4399
SERVER_HOST=0.0.0.0
API_ENDPOINT=/api/v1
SERVER_LOG_FILE=/path/to/server.log
POSTGRE_URI=postgresql:///main

# LLM Provider Keys (at least one)
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
MOONSHOT_API_KEY=...
```

### VSCode Extension Development

```bash
# Install dependencies for plugin
pnpm run install-plugin

# Build plugin views (in watch mode)
pnpm run views:dev

# Build plugin views (production)
pnpm run views:build

# Copy views to plugin
pnpm run views:copy
```

## Code Style Guidelines

### TypeScript
- Use strict mode (`strict: true` in tsconfig)
- Target ES2024
- Use ES modules (`"type": "module"`)
- Path mapping via `@saili/*` imports
- Jest for testing with ESM support

### Python
- Use UTF-8 encoding for all files (especially on Windows)
- File headers follow this format:
```python
# -*- coding: utf-8 -*-
# @file filename.py
# @brief Brief description
# @author sailing-innocent
# @date YYYY-MM-DD
# @version 1.0
# ---------------------------------
```
- Ruff linting with minimal rules (F, W, T, S102, S307)
- Type hints encouraged

## Key Architecture Patterns

### Backend (Python)
- **Router-Controller-Model** pattern
- **Dependency Injection**: Uses Litestar's DI system with `Provide`
- **Database**: SQLAlchemy 2.0 with session management via `g_db_func` generator
- **API Structure**: `/api/v1/<domain>` endpoints

### Frontend Site (React)
- **State Management**: Zustand stores in `lib/store/`
- **API Layer**: TypeScript API clients in `lib/api/`
- **Data Layer**: Data transformation utilities in `lib/data/`
- **Components**: Feature-based organization with shared `ui/` components

### VSCode Extension
- **Command Pattern**: All commands in `commands/` directory
- **Workspace Management**: Multiple workspace types supported
- **Engine Integration**: Communicates with Dendron engine
- **Webviews**: React-based views in separate package

## Security Considerations

- Environment files (`.env.*`) are gitignored
- API keys for LLM providers must be kept secure
- Database credentials in environment variables
- CORS configured to allow all origins in development (`allow_origins=["*"]`)
- Log files may contain sensitive data - review before sharing

## Domain Modules

The application is organized around these domains:

1. **Finance** (`/money`): Account management, transactions, budgets
2. **Health** (`/health`): Weight tracking, health metrics
3. **Project** (`/project`): Mission boards, task management
4. **Text** (`/text`): Text import, chapter management, reading
5. **Analysis** (`/analysis`): Character profiles, outlines, settings extraction
6. **Necessity** (`/necessity`): Inventory, residence, journey tracking
7. **History** (`/history`): Timeline events tracking

## Version Management

All packages use synchronized versioning (currently 0.2.4):

```bash
# Bump version (patch, minor, major)
pnpm run version:patch
pnpm run version:minor
pnpm run version:major
```

This updates all package.json files to the same version.

## Notes for AI Agents

- This is a personal project with Chinese and English mixed in comments
- Many comments and docstrings are in Chinese
- The project evolved from Dendron - some code retains "dendron" naming
- The Python backend uses a custom task dispatcher pattern for background jobs
- LLM integration supports multiple providers with fallback
- Database migrations are handled manually (check `sail_server/migration/`)
