# CHANGELOG

<!-- version list -->

## v1.6.0 (2026-03-26)

### Features

- Add project tag management tools
  ([`7d425c1`](https://github.com/TETRA-2023/pytaiga-mcp/commit/7d425c15ee69c4dbe3b046ab98a900fa8bcd3716))


## v1.5.0 (2026-03-26)

### Features

- Add global search tool and CLAUDE.md
  ([`0c9981b`](https://github.com/TETRA-2023/pytaiga-mcp/commit/0c9981bde6bd41bd6b3f7b2f634fee1345a3fa80))


## v1.4.0 (2026-03-24)

### Bug Fixes

- Bind SSE/HTTP server to MCP_HOST for Docker compatibility
  ([`01edeb4`](https://github.com/TETRA-2023/pytaiga-mcp/commit/01edeb4b8371b7b57b6045dda2ac10e50dc6f899))

- Validate MCP_PORT and document MCP_HOST/MCP_PORT env vars
  ([`09c10a2`](https://github.com/TETRA-2023/pytaiga-mcp/commit/09c10a263dd630cfcee4d88b20ba78ea52863eea))

### Features

- Add update, delete, and get-by-slug wiki page tools
  ([`f43e346`](https://github.com/TETRA-2023/pytaiga-mcp/commit/f43e346577a1cf747d68497b16cb8f58c4005e0b))


## v1.3.1 (2026-03-24)

### Bug Fixes

- Bind SSE/HTTP server to MCP_HOST for Docker compatibility
  ([`c80d1b0`](https://github.com/TETRA-2023/pytaiga-mcp/commit/c80d1b0d49bebbec15d679f337ac4e035db12640))


## v1.3.0 (2026-03-24)

### Features

- Add SSE and streamable-http transport support
  ([`ede5586`](https://github.com/TETRA-2023/pytaiga-mcp/commit/ede5586c526b3cfde73e1d8f7c821a6d37b25434))


## v1.2.3 (2026-03-16)

### Bug Fixes

- Disable pagination on all list calls via x-disable-pagination header
  ([`ce35ae4`](https://github.com/TETRA-2023/pytaiga-mcp/commit/ce35ae46fc228633552211c00a6e392d405fa8c1))


## v1.2.2 (2026-03-15)

### Bug Fixes

- **server**: Handle invalid JSON gracefully in _parse_mcp_kwargs
  ([`355e6a8`](https://github.com/TETRA-2023/pytaiga-mcp/commit/355e6a8c8da95c209fc72d5d3e214c929ec6fb05))

- **server**: Set default session on login and use correct slug lookup
  ([`2148586`](https://github.com/TETRA-2023/pytaiga-mcp/commit/2148586bdf60fa93b5ba9342df41d36a42a8c732))

### Documentation

- Update README for Python 3.12, GHCR image, pre-commit hooks
  ([`d28ffc2`](https://github.com/TETRA-2023/pytaiga-mcp/commit/d28ffc2db91e2f4384690025e75370a070382327))

### Testing

- Add filters key path coverage for _parse_mcp_kwargs
  ([`30681e5`](https://github.com/TETRA-2023/pytaiga-mcp/commit/30681e5b0c15c6a8badc95f3619a4df3acb083dc))

- Remove duplicate get_project_by_slug test
  ([`662438c`](https://github.com/TETRA-2023/pytaiga-mcp/commit/662438ce8493eaeded0c7e87d7b122df0268c394))


## v1.2.1 (2026-03-15)

### Bug Fixes

- **ci**: Bump GitHub Actions to Node.js 24 compatible versions
  ([`0c105a4`](https://github.com/TETRA-2023/pytaiga-mcp/commit/0c105a46d42185c7196241d4c66c6f04406d6ce9))


## v1.2.0 (2026-03-15)

### Bug Fixes

- Align requires-python and ruff target to 3.12 matching CI
  ([`70a7e0e`](https://github.com/TETRA-2023/pytaiga-mcp/commit/70a7e0e1be3450f875b89c7547d9d73dd2c56d55))

- **ci**: Add contents:read permission, lowercase GHCR tags, robust version extraction
  ([`1bcd6e7`](https://github.com/TETRA-2023/pytaiga-mcp/commit/1bcd6e7d161d569720b1605c5e5ac9dd958b7ce6))

- **ci**: Align ruff version between pre-commit and CI, standardize Python 3.12
  ([`191edf1`](https://github.com/TETRA-2023/pytaiga-mcp/commit/191edf139e4b8339f09267e49e4c617ab9ece80f))

- **ci**: Validate Docker tag version, decouple release from docker, drop Python matrix
  ([`43a122c`](https://github.com/TETRA-2023/pytaiga-mcp/commit/43a122cdc455f784183f0cd9400483b62d8a7473))

### Features

- **ci**: Add Docker image build and push to GHCR
  ([`29136c6`](https://github.com/TETRA-2023/pytaiga-mcp/commit/29136c6511fc083833ef7e90cbbfc75ada645fc4))

- **dev**: Add pre-commit hooks for ruff lint, format, and unit tests
  ([`4f85e56`](https://github.com/TETRA-2023/pytaiga-mcp/commit/4f85e565953d83feabf6abb18792c9f46cf3dae3))


## v1.0.1 (2026-02-09)

### Bug Fixes

- **server**: Implement .edit() for partial updates and harden integration tests
  ([`73f1171`](https://github.com/talhaorak/pytaiga-mcp/commit/73f1171cb44e7671014a792b4b6033c964711446))

### Code Style

- **verify**: Use dict literals for kwargs in verify_tools.py
  ([`f36f891`](https://github.com/talhaorak/pytaiga-mcp/commit/f36f891da3159ed9589a72c735b7a36eaf72bd47))

### Refactoring

- Address PR review feedback (fix api access, harden updates, clean tests)
  ([`67bb0bd`](https://github.com/talhaorak/pytaiga-mcp/commit/67bb0bd5114a0a2d3cc0e339771432c2d8341c75))

### Testing

- Align unit tests with new .edit() usage in update_project
  ([`31681a3`](https://github.com/talhaorak/pytaiga-mcp/commit/31681a3a5ec68ce71f7ce2a869750a8a1c43296c))


## v1.0.0 (2026-02-06)

- Initial Release
