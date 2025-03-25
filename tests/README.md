# Taiga MCP Bridge Tests

This directory contains tests for the Taiga MCP Bridge.

## Directory Structure

```
tests/
├── conftest.py             # Shared pytest fixtures
├── unit/                   # Unit tests
│   ├── test_auth.py        # Authentication tests
│   ├── test_client_core.py # Client core functionality tests
│   ├── test_projects.py    # Project-related tests
│   ├── test_epics.py       # Epic-related tests
│   ├── test_user_stories.py# User story-related tests
│   └── test_server.py      # Server initialization tests
└── integration/            # Integration tests
    └── test_client_integration.py # Tests with mocked HTTP endpoints
```

## Running Tests

To run all tests:

```bash
pytest
```

To run only unit tests:

```bash
pytest tests/unit/
```

To run only integration tests:

```bash
pytest tests/integration/
```

To run tests with specific markers:

```bash
pytest -m "auth"  # Authentication tests
pytest -m "core"  # Core functionality tests
pytest -m "projects"  # Project-related tests
```

To run tests with coverage:

```bash
pytest --cov=src
```

## Test Configuration

Test configuration is defined in `pyproject.toml` in the root directory under the `[tool.pytest.ini_options]` section, which includes:

- Test paths
- Markers
- Python file and function patterns
- Command-line options

## Test Markers

- `unit`: Unit tests
- `integration`: Integration tests
- `slow`: Slow-running tests
- `auth`: Authentication tests
- `core`: Core functionality tests
- `projects`: Project-related tests
- `epics`: Epic-related tests
- `user_stories`: User story-related tests
- `tasks`: Task-related tests
- `issues`: Issue-related tests
- `sprints`: Sprint-related tests

## Using Test Fixtures

Our tests use fixtures defined in `conftest.py` for shared resources:

```python
# Example test using shared fixtures
def test_authenticate_success(taiga_client, mock_taiga_api, mock_uuid):
    # Use the fixtures to test authentication
    result = taiga_client.authenticate("valid", "valid")
    assert result["status"] == "authenticated"
```

## Adding New Tests

1. Create a test file in the appropriate directory
2. Use the existing fixtures from `conftest.py` when possible
3. Follow the Arrange-Act-Assert pattern for test organization
4. Use descriptive test names that explain what's being tested
5. Add appropriate markers to categorize your tests

```python
# Example new test
@pytest.mark.projects
def test_new_feature(authenticated_client, mock_project):
    # Arrange
    client, session_id = authenticated_client
    # ...setup test data...
    
    # Act
    result = client.some_method()
    
    # Assert
    assert result["status"] == "success"
```

## Integration Tests

Integration tests use the `responses` library to mock HTTP requests:

```python
@pytest.mark.integration
@responses.activate
def test_api_interaction(taiga_client_with_real_http, taiga_base_url):
    # Mock HTTP endpoints
    responses.add(
        responses.POST,
        f"{taiga_base_url}/api/v1/auth",
        json={"auth_token": "dummy-token"}
    )
    
    # Test code that makes HTTP requests
    # ...
``` 