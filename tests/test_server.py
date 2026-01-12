import uuid
from unittest.mock import MagicMock, patch

import pytest

# Import the server module instead of specific functions
import src.server
from src.taiga_client import TaigaClientWrapper

# Test constants
TEST_HOST = "https://your-test-taiga-instance.com"
TEST_USERNAME = "test_user"
TEST_PASSWORD = "test_password"

class TestTaigaTools:
    @pytest.fixture
    def session_setup(self):
        """Create a session setup for testing"""
        # Generate a session ID
        session_id = str(uuid.uuid4())

        # Create and return a mock client
        mock_client = MagicMock()
        mock_client.is_authenticated = True

        # Store the mock client in active_sessions
        src.server.active_sessions[session_id] = mock_client

        return session_id, mock_client

    def test_login(self):
        """Test the login functionality"""
        with patch.object(TaigaClientWrapper, 'login', return_value=True):
            # Clear any existing sessions
            src.server.active_sessions.clear()

            # Call the login function
            result = src.server.login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)

            # Verify results
            assert "session_id" in result
            assert result["session_id"] in src.server.active_sessions

            # Cleanup
            src.server.active_sessions.clear()

    def test_list_projects(self, session_setup):
        """Test list_projects functionality"""
        session_id, mock_client = session_setup

        # Setup list projects return - return actual dictionaries
        mock_client.api.projects.list.return_value = [{"id": 123, "name": "Test Project"}]

        # List projects and verify
        projects = src.server.list_projects(session_id)
        assert len(projects) == 1
        assert projects[0]["name"] == "Test Project"
        assert projects[0]["id"] == 123

    def test_update_project(self, session_setup):
        """Test update_project functionality"""
        session_id, mock_client = session_setup

        # Setup get project return with version (needed for update)
        mock_client.api.projects.get.return_value = {"id": 123, "name": "Old Name", "version": 1}

        # Setup update return
        mock_client.api.projects.update.return_value = {"id": 123, "name": "New Name", "version": 2}

        # Update the project name - kwargs as JSON string, then session_id
        result = src.server.update_project(123, '{"name": "New Name"}', session_id)

        # Verify the update was called with correct parameters
        mock_client.api.projects.update.assert_called_once_with(
            project_id=123,
            version=1,
            project_data={"name": "New Name"}
        )
        assert result["name"] == "New Name"

    def test_list_user_stories(self, session_setup):
        """Test list_user_stories functionality"""
        session_id, mock_client = session_setup

        # Setup list user stories return - return actual dictionaries
        mock_client.api.user_stories.list.return_value = [{"id": 456, "subject": "Test User Story"}]

        # List user stories and verify - filters as JSON string (empty), then session_id
        stories = src.server.list_user_stories(123, "{}", session_id)
        assert len(stories) == 1
        assert stories[0]["subject"] == "Test User Story"
        assert stories[0]["id"] == 456

        # Verify the correct project filter was used
        mock_client.api.user_stories.list.assert_called_once_with(project=123)

    def test_create_user_story(self, session_setup):
        """Test create_user_story functionality"""
        session_id, mock_client = session_setup

        # Setup create user story return - return actual dictionary
        mock_client.api.user_stories.create.return_value = {"id": 456, "subject": "New Story"}

        # Create user story and verify - kwargs as JSON string, then session_id
        story = src.server.create_user_story(123, "New Story", '{"description": "Test description"}', session_id)
        assert story["subject"] == "New Story"
        assert story["id"] == 456

        # Verify the create was called with correct parameters
        mock_client.api.user_stories.create.assert_called_once_with(project=123, subject="New Story", description="Test description")

    def test_list_tasks(self, session_setup):
        """Test list_tasks functionality"""
        session_id, mock_client = session_setup

        # Setup list tasks return - the code uses api.get("/tasks") instead of api.tasks.list()
        # due to a pytaigaclient bug workaround
        mock_client.api.get.return_value = [{"id": 789, "subject": "Test Task"}]

        # List tasks and verify - filters as JSON string (empty), then session_id
        tasks = src.server.list_tasks(123, "{}", session_id)
        assert len(tasks) == 1
        assert tasks[0]["subject"] == "Test Task"
        assert tasks[0]["id"] == 789

        # Verify the correct API call was made (uses get instead of tasks.list due to bug workaround)
        mock_client.api.get.assert_called_once_with("/tasks", params={"project": 123})


class TestResponseFiltering:
    """Tests for the response filtering functionality."""

    def test_filter_standard_always_includes_version(self):
        """version is required for updates in standard level."""
        for resource_type, levels in src.server.RESPONSE_FIELDS.items():
            if resource_type != "member":  # member doesn't have version
                assert "version" in levels["standard"], f"{resource_type} missing version in standard"

    def test_filter_minimal_includes_id(self):
        """All minimal levels must include id."""
        for resource_type, levels in src.server.RESPONSE_FIELDS.items():
            assert "id" in levels["minimal"], f"{resource_type} missing id in minimal"

    def test_filter_minimal_includes_project_where_applicable(self):
        """Resources with project association must include project in minimal."""
        project_resources = ["user_story", "task", "issue", "epic", "milestone", "wiki_page"]
        for resource_type in project_resources:
            assert "project" in src.server.RESPONSE_FIELDS[resource_type]["minimal"], \
                f"{resource_type} missing project in minimal"

    def test_filter_response_handles_none(self):
        """_filter_response should return None when given None."""
        assert src.server._filter_response(None, "user_story") is None

    def test_filter_response_handles_empty_list(self):
        """_filter_response should return empty list when given empty list."""
        assert src.server._filter_response([], "user_story") == []

    def test_filter_response_unknown_type_returns_full(self):
        """Unknown resource types should return full response."""
        data = {"id": 1, "extra": "field"}
        assert src.server._filter_response(data, "unknown_type") == data

    def test_filter_response_full_verbosity_returns_all(self):
        """Full verbosity should return all fields."""
        data = {"id": 1, "subject": "Test", "version": 1, "watchers": [1, 2], "extra_field": "value"}
        result = src.server._filter_response(data, "user_story", verbosity="full")
        assert result == data

    def test_filter_response_standard_filters_fields(self):
        """Standard verbosity should filter to defined fields."""
        data = {
            "id": 1, "ref": 123, "subject": "Test", "description": "Desc",
            "status": 1, "version": 2,
            "watchers": [1, 2], "extra_internal_field": "should_be_filtered"
        }
        result = src.server._filter_response(data, "user_story", verbosity="standard")
        assert "id" in result
        assert "ref" in result
        assert "subject" in result
        assert "version" in result
        assert "watchers" not in result
        assert "extra_internal_field" not in result

    def test_filter_response_minimal_filters_to_core(self):
        """Minimal verbosity should filter to core identification fields."""
        data = {
            "id": 1, "ref": 123, "subject": "Test", "status": 1, "project": 10,
            "description": "Long description", "version": 2, "watchers": [1, 2]
        }
        result = src.server._filter_response(data, "user_story", verbosity="minimal")
        assert result == {"id": 1, "ref": 123, "subject": "Test", "status": 1, "project": 10}

    def test_filter_response_list_filters_each_item(self):
        """_filter_response should filter each item in a list."""
        data = [
            {"id": 1, "subject": "Story 1", "watchers": [1]},
            {"id": 2, "subject": "Story 2", "watchers": [2]}
        ]
        result = src.server._filter_response(data, "user_story", verbosity="minimal")
        assert len(result) == 2
        assert "watchers" not in result[0]
        assert "watchers" not in result[1]

    def test_filter_response_invalid_verbosity_falls_back_to_standard(self):
        """Typos in verbosity should warn and use standard."""
        data = {"id": 1, "subject": "Test", "version": 1, "watchers": [1, 2]}
        result = src.server._filter_response(data, "user_story", verbosity="stanard")  # typo
        assert "id" in result
        assert "version" in result
        assert "watchers" not in result
