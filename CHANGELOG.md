# CHANGELOG

<!-- version list -->

## v2.0.0 (2026-03-17)
### Major Release — 32 New Tools (62 → 94 total)
### New Features
- **Search**: Full-text search across all item types (`search`)
- **Bulk Operations**: `bulk_create_user_stories`, `bulk_create_tasks`, `bulk_create_epics`, `bulk_update_story_sprint`
- **Project Stats**: `get_project_stats`, `get_project_issue_stats`, `get_milestone_stats`
- **Custom Attributes**: `list_custom_attributes`, `get_custom_attribute_values`, `set_custom_attribute_values`
- **History & Timeline**: `get_history`, `get_project_timeline`, `get_user_timeline`
- **Watch & Vote**: `watch_item`, `unwatch_item`, `upvote_item`, `downvote_item`
- **Wiki Complete**: `update_wiki_page`, `delete_wiki_page`, `list_wiki_links`, `create_wiki_link`, `delete_wiki_link`
- **Tags**: `get_project_tags`, `create_project_tag`, `delete_project_tag`
- **Roles & Points**: `list_roles`, `list_points`
- **Filters**: `get_filters_data`
- **Resolver**: `resolve`
- **Attachments**: `list_attachments`, `delete_attachment`

## v1.1.1 (2026-03-16)

### Bug Fixes

- **server**: Handle invalid JSON gracefully in _parse_mcp_kwargs
  ([`355e6a8`](https://github.com/talhaorak/pytaiga-mcp/commit/355e6a8c8da95c209fc72d5d3e214c929ec6fb05))

### Testing

- Add filters key path coverage for _parse_mcp_kwargs
  ([`30681e5`](https://github.com/talhaorak/pytaiga-mcp/commit/30681e5b0c15c6a8badc95f3619a4df3acb083dc))


## v1.1.0 (2026-03-16)

### Bug Fixes

- Align requires-python and ruff target to 3.12 matching CI
  ([`70a7e0e`](https://github.com/talhaorak/pytaiga-mcp/commit/70a7e0e1be3450f875b89c7547d9d73dd2c56d55))

- Run Docker image as non-root without permission errors
  ([`b159f1a`](https://github.com/talhaorak/pytaiga-mcp/commit/b159f1ab2b22262af0fc7c82a4fc88a63a2738b3))

- **ci**: Add contents:read permission, lowercase GHCR tags, robust version extraction
  ([`1bcd6e7`](https://github.com/talhaorak/pytaiga-mcp/commit/1bcd6e7d161d569720b1605c5e5ac9dd958b7ce6))

- **ci**: Align ruff version between pre-commit and CI, standardize Python 3.12
  ([`191edf1`](https://github.com/talhaorak/pytaiga-mcp/commit/191edf139e4b8339f09267e49e4c617ab9ece80f))

- **ci**: Bump GitHub Actions to Node.js 24 compatible versions
  ([`0c105a4`](https://github.com/talhaorak/pytaiga-mcp/commit/0c105a46d42185c7196241d4c66c6f04406d6ce9))

- **ci**: Remove redundant pytest.ini and add Python 3.13 to test matrix
  ([`6724cf2`](https://github.com/talhaorak/pytaiga-mcp/commit/6724cf27dfdcb4cff477e975f40ff6358d5a294d))

- **ci**: Validate Docker tag version, decouple release from docker, drop Python matrix
  ([`43a122c`](https://github.com/talhaorak/pytaiga-mcp/commit/43a122cdc455f784183f0cd9400483b62d8a7473))

- **deps**: Upgrade transitive dependencies to resolve 12 security alerts
  ([`ca1b153`](https://github.com/talhaorak/pytaiga-mcp/commit/ca1b153b9d79ce8cceabe7f386ea50263f3a045c))

- **server**: Set default session on login and use correct slug lookup
  ([`2148586`](https://github.com/talhaorak/pytaiga-mcp/commit/2148586bdf60fa93b5ba9342df41d36a42a8c732))

### Documentation

- Update README for Python 3.12, GHCR image, pre-commit hooks
  ([`d28ffc2`](https://github.com/talhaorak/pytaiga-mcp/commit/d28ffc2db91e2f4384690025e75370a070382327))

### Features

- Add Docker support
  ([`9971b60`](https://github.com/talhaorak/pytaiga-mcp/commit/9971b607e9b7dcfbf21c4c10bd6b665754b63acb))

- **ci**: Add Docker image build and push to GHCR
  ([`29136c6`](https://github.com/talhaorak/pytaiga-mcp/commit/29136c6511fc083833ef7e90cbbfc75ada645fc4))

- **dev**: Add pre-commit hooks for ruff lint, format, and unit tests
  ([`4f85e56`](https://github.com/talhaorak/pytaiga-mcp/commit/4f85e565953d83feabf6abb18792c9f46cf3dae3))

### Testing

- Remove duplicate get_project_by_slug test
  ([`662438c`](https://github.com/talhaorak/pytaiga-mcp/commit/662438ce8493eaeded0c7e87d7b122df0268c394))


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
