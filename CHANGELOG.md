# CHANGELOG

<!-- version list -->

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
