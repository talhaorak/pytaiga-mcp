# CLAUDE.md — pytaiga-mcp

## Project Overview

MCP (Model Context Protocol) server bridging AI assistants with the Taiga project management API. Built on FastMCP with the `pytaigaclient` library.

- **Package**: `mcp-taiga-bridge`
- **Python**: >= 3.12
- **Upstream**: `talhaorak/pytaiga-mcp` (origin: `TETRA-2023/pytaiga-mcp`)

## Architecture

```
src/
  server.py        — MCP tool definitions (all 64+ tools registered via @mcp.tool())
  taiga_client.py  — TaigaClientWrapper: auth, raw API calls, pagination bypass
  config.py        — Pydantic settings (env vars, SecretStr credentials)
```

- `server.py` is the main file (~2300 lines). Tools are grouped by resource type: auth, projects, user stories, tasks, issues, epics, milestones, wiki, memberships, comments.
- `taiga_client.py` wraps `pytaigaclient.TaigaClient` and adds `list_resources()` with `x-disable-pagination` header.
- Session management: `active_sessions` dict keyed by UUID (or `"default"` for auto-auth).

## Development Setup

```bash
./install.sh --dev    # Install with dev dependencies (ruff, pytest, mypy, pre-commit)
cp .env.example .env  # Configure TAIGA_API_URL, TAIGA_USERNAME, TAIGA_PASSWORD
```

## Running

```bash
./run.sh              # stdio transport (default)
./run.sh --sse        # SSE transport
# Or directly:
uv run python src/server.py [--sse | --streamable-http]
```

Environment variables: `TAIGA_TRANSPORT`, `TAIGA_API_URL`, `TAIGA_USERNAME`, `TAIGA_PASSWORD`, `MCP_HOST`, `MCP_PORT`.

## Testing

```bash
./run_unit_tests.sh                                        # Unit tests only
uv run pytest tests/test_server.py -v                      # Unit tests
uv run pytest tests/test_integration.py -v -m integration  # Integration tests (needs running Taiga)
```

Pre-commit hooks run ruff (lint + format) and unit tests automatically.

## Code Conventions

- **Linter/formatter**: ruff (line-length=100, target py312, rules: E, F, W, I)
- **Commit messages**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, etc.) — used by `python-semantic-release` for auto-versioning
- **Branch naming**: `feature/<name>`, `fix/<name>`
- **Tool pattern**: Each Taiga resource follows a consistent CRUD pattern:
  - `list_{resource}`, `create_{resource}`, `get_{resource}`, `get_{resource}_by_ref`, `update_{resource}`, `delete_{resource}`
  - `assign_{resource}_to_user` / `unassign_{resource}_from_user` where applicable
  - `get_{resource}_statuses` for status lookups
- **Kwargs validation**: All create/update tools validate kwargs against `ALLOWED_KWARGS[resource_type]`
- **Response filtering**: `verbosity` parameter ("minimal", "standard", "full") controls returned fields via `RESPONSE_FIELDS` dict
- **Error handling**: All tools use `_execute_taiga_operation()` wrapper for consistent error handling
- **Security**: Never log credentials. Use `SecretStr` for passwords. Validate kwargs against allowlists.

## Key Design Decisions

- Pagination disabled globally via `x-disable-pagination: True` header (Taiga default PAGE_SIZE=30 is too low)
- Comments use raw HTTP (PATCH with version for optimistic concurrency, GET history for listing)
- `link_user_story_to_epic` uses raw POST to `/epics/{id}/related_userstories`
- `_COMMENT_TYPE_MAP` translates user-facing types to API path segments

## Contributing

Per CONTRIBUTING.md:
1. Create feature branch (`feature/<name>`)
2. Install dev dependencies (`./install.sh --dev`)
3. Make changes following the code conventions above
4. Run tests (`uv run pytest tests/test_server.py -v`)
5. Ensure ruff passes (`uv run ruff check src/ && uv run ruff format --check src/`)
6. Commit with conventional commit messages
7. Open a Pull Request

**Repository policy**: This is a maintained fork. All PRs must target `TETRA-2023/pytaiga-mcp`. Do not open PRs against the upstream repo (`talhaorak/pytaiga-mcp`) — contributions to upstream should be coordinated separately and manually by maintainers.

**Branch retention**: Do not delete branches after merging. Merged branches are kept to facilitate cherry-picking and PR transfers to upstream.

The project follows the Contributor Covenant Code of Conduct v2.0.
