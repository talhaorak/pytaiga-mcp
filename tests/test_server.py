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


# ─── Helper fixtures ──────────────────────────────────────────────────


class TestTaigaTools:
    @pytest.fixture
    def session_setup(self):
        """Create a session setup for testing"""
        session_id = str(uuid.uuid4())
        mock_client = MagicMock()
        mock_client.is_authenticated = True
        src.server.active_sessions[session_id] = mock_client
        yield session_id, mock_client
        src.server.active_sessions.pop(session_id, None)

    # ─── Authentication tests ─────────────────────────────────────────

    def test_login(self):
        """Test the login functionality"""
        with patch.object(TaigaClientWrapper, "login", return_value=True):
            src.server.active_sessions.clear()
            result = src.server.login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)
            assert "session_id" in result
            assert result["session_id"] in src.server.active_sessions
            src.server.active_sessions.clear()

    def test_login_missing_host(self):
        """Test login raises error when host is missing."""
        with patch("src.server.settings") as mock_settings:
            mock_settings.host = None
            mock_settings.get_username_value.return_value = TEST_USERNAME
            mock_settings.get_password_value.return_value = TEST_PASSWORD
            with pytest.raises(ValueError, match="Host URL required"):
                src.server.login(None, TEST_USERNAME, TEST_PASSWORD)

    def test_login_missing_credentials(self):
        """Test login raises error when credentials are missing."""
        with patch("src.server.settings") as mock_settings:
            mock_settings.host = TEST_HOST
            mock_settings.get_username_value.return_value = None
            mock_settings.get_password_value.return_value = None
            with pytest.raises(ValueError, match="Credentials required"):
                src.server.login(TEST_HOST, None, None)

    def test_login_failure(self):
        """Test login raises error on authentication failure."""
        with patch.object(TaigaClientWrapper, "login", return_value=False):
            with pytest.raises(RuntimeError, match="unexpected server error occurred during login"):
                src.server.login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)

    # ─── Session management tests ─────────────────────────────────────

    def test_get_default_session_available(self, session_setup):
        """Test get_default_session when default session exists."""
        session_id, mock_client = session_setup
        src.server.active_sessions["default"] = mock_client
        try:
            result = src.server.get_default_session()
            assert result["status"] == "active"
            assert result["session_id"] == "default"
            assert result["auto_authenticated"] is True
        finally:
            src.server.active_sessions.pop("default", None)

    def test_get_default_session_unavailable(self):
        """Test get_default_session when no default session exists."""
        src.server.active_sessions.pop("default", None)
        result = src.server.get_default_session()
        assert result["status"] == "unavailable"

    def test_logout(self, session_setup):
        """Test logout removes session."""
        session_id, mock_client = session_setup
        result = src.server.logout(session_id)
        assert result["status"] == "logged_out"
        assert session_id not in src.server.active_sessions

    def test_logout_nonexistent_session(self):
        """Test logout with a non-existent session."""
        fake_id = str(uuid.uuid4())
        # Need a default session or it will raise ValueError
        mock_client = MagicMock()
        mock_client.is_authenticated = True
        src.server.active_sessions["default"] = mock_client
        try:
            result = src.server.logout(fake_id)
            assert result["status"] == "session_not_found"
        finally:
            src.server.active_sessions.pop("default", None)

    def test_session_status_active(self, session_setup):
        """Test session_status for an active session."""
        session_id, mock_client = session_setup
        mock_client.api.users.get_me.return_value = {"username": "test_user"}
        result = src.server.session_status(session_id)
        assert result["status"] == "active"
        assert result["username"] == "test_user"

    def test_session_status_inactive(self):
        """Test session_status for a non-existent session."""
        fake_id = str(uuid.uuid4())
        mock_client = MagicMock()
        mock_client.is_authenticated = True
        src.server.active_sessions["default"] = mock_client
        try:
            result = src.server.session_status(fake_id)
            assert result["status"] == "inactive"
            assert result["reason"] == "not_found"
        finally:
            src.server.active_sessions.pop("default", None)

    # ─── Helper function tests ────────────────────────────────────────

    def test_get_session_id_with_explicit(self, session_setup):
        """Test _get_session_id returns explicit session_id."""
        session_id, _ = session_setup
        assert src.server._get_session_id(session_id) == session_id

    def test_get_session_id_default(self, session_setup):
        """Test _get_session_id returns default when available."""
        _, mock_client = session_setup
        src.server.active_sessions["default"] = mock_client
        try:
            assert src.server._get_session_id(None) == "default"
        finally:
            src.server.active_sessions.pop("default", None)

    def test_get_session_id_raises_without_default(self):
        """Test _get_session_id raises ValueError when no default session."""
        src.server.active_sessions.clear()
        with pytest.raises(ValueError, match="No session_id provided"):
            src.server._get_session_id(None)

    def test_get_authenticated_client_invalid(self):
        """Test _get_authenticated_client raises for invalid session."""
        with pytest.raises(PermissionError, match="Invalid or expired session"):
            src.server._get_authenticated_client("nonexistent-session")

    def test_execute_taiga_operation_success(self):
        """Test _execute_taiga_operation returns result on success."""
        result = src.server._execute_taiga_operation("test_op", lambda: {"ok": True})
        assert result == {"ok": True}

    def test_execute_taiga_operation_runtime_error(self):
        """Test _execute_taiga_operation wraps unexpected errors."""

        def failing():
            raise Exception("something broke")

        with pytest.raises(RuntimeError, match="Server error in test_op"):
            src.server._execute_taiga_operation("test_op", failing)

    # ─── kwargs parsing and validation tests ──────────────────────────

    def test_parse_mcp_kwargs_empty(self):
        """Test parsing empty kwargs."""
        assert src.server._parse_mcp_kwargs({}) == {}

    def test_parse_mcp_kwargs_json_string(self):
        """Test parsing kwargs with JSON string."""
        result = src.server._parse_mcp_kwargs({"kwargs": '{"name": "test"}'})
        assert result == {"name": "test"}

    def test_parse_mcp_kwargs_dict(self):
        """Test parsing kwargs with dict value."""
        result = src.server._parse_mcp_kwargs({"kwargs": {"name": "test"}})
        assert result == {"name": "test"}

    def test_parse_mcp_kwargs_passthrough(self):
        """Test parsing kwargs with multiple keys passes through."""
        data = {"name": "test", "desc": "value"}
        assert src.server._parse_mcp_kwargs(data) == data

    def test_validate_kwargs_strips_unexpected(self):
        """Test _validate_kwargs strips unexpected fields."""
        result = src.server._validate_kwargs("project", {"name": "test", "invalid_field": "value"})
        assert result == {"name": "test"}

    def test_validate_kwargs_strict_raises(self):
        """Test _validate_kwargs raises in strict mode."""
        with pytest.raises(ValueError, match="Unexpected kwargs"):
            src.server._validate_kwargs(
                "project", {"name": "test", "invalid_field": "value"}, strict=True
            )

    def test_validate_kwargs_empty(self):
        """Test _validate_kwargs with empty dict."""
        assert src.server._validate_kwargs("project", {}) == {}

    def test_validate_kwargs_unknown_resource(self):
        """Test _validate_kwargs with unknown resource type passes through."""
        data = {"any": "field"}
        assert src.server._validate_kwargs("unknown_type", data) == data

    # ─── Project tools tests ─────────────────────────────────────────

    def test_list_projects(self, session_setup):
        """Test list_projects functionality"""
        session_id, mock_client = session_setup
        mock_client.api.projects.list.return_value = [{"id": 123, "name": "Test Project"}]
        projects = src.server.list_projects(session_id)
        assert len(projects) == 1
        assert projects[0]["name"] == "Test Project"
        assert projects[0]["id"] == 123

    def test_list_all_projects(self, session_setup):
        """Test list_all_projects delegates to list_projects."""
        session_id, mock_client = session_setup
        mock_client.api.projects.list.return_value = [{"id": 1, "name": "P1"}]
        projects = src.server.list_all_projects(session_id)
        assert len(projects) == 1

    def test_get_project(self, session_setup):
        """Test get_project returns project by ID."""
        session_id, mock_client = session_setup
        mock_client.api.projects.get.return_value = {
            "id": 123,
            "name": "Test",
            "slug": "test",
            "version": 1,
        }
        result = src.server.get_project(123, session_id)
        assert result["id"] == 123
        mock_client.api.projects.get.assert_called_once_with(123)

    def test_get_project_by_slug(self, session_setup):
        """Test get_project_by_slug returns project by slug."""
        session_id, mock_client = session_setup
        mock_client.api.projects.get.return_value = {
            "id": 123,
            "name": "Test",
            "slug": "test-slug",
            "version": 1,
        }
        result = src.server.get_project_by_slug("test-slug", session_id)
        assert result["slug"] == "test-slug"
        mock_client.api.projects.get.assert_called_once_with(slug="test-slug")

    def test_create_project(self, session_setup):
        """Test create_project creates a project."""
        session_id, mock_client = session_setup
        mock_client.api.projects.create.return_value = {
            "id": 456,
            "name": "New Project",
            "slug": "new-project",
            "version": 1,
        }
        result = src.server.create_project("New Project", "A description", "{}", session_id)
        assert result["id"] == 456
        assert result["name"] == "New Project"
        mock_client.api.projects.create.assert_called_once_with(
            name="New Project", description="A description"
        )

    def test_create_project_with_kwargs(self, session_setup):
        """Test create_project with extra kwargs."""
        session_id, mock_client = session_setup
        mock_client.api.projects.create.return_value = {
            "id": 456,
            "name": "Private Project",
            "is_private": True,
            "version": 1,
        }
        result = src.server.create_project(
            "Private Project", "Desc", '{"is_private": true}', session_id
        )
        assert result["id"] == 456
        mock_client.api.projects.create.assert_called_once_with(
            name="Private Project", description="Desc", is_private=True
        )

    def test_create_project_empty_name(self, session_setup):
        """Test create_project raises error for empty name."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Project name and description are required"):
            src.server.create_project("", "desc", "{}", session_id)

    def test_update_project(self, session_setup):
        """Test update_project functionality with version."""
        session_id, mock_client = session_setup
        mock_client.api.projects.get.return_value = {"id": 123, "name": "Old Name", "version": 1}
        mock_client.api.projects.update.return_value = {"id": 123, "name": "New Name", "version": 2}
        result = src.server.update_project(123, '{"name": "New Name"}', session_id)
        mock_client.api.projects.update.assert_called_once_with(
            project_id=123, project_data={"name": "New Name"}, version=1
        )
        assert result["name"] == "New Name"

    def test_update_project_without_version(self, session_setup):
        """Test update_project when project has no version field (Taiga projects)."""
        session_id, mock_client = session_setup
        mock_client.api.projects.get.return_value = {"id": 123, "name": "Old Name"}
        mock_client.api.patch.return_value = {"id": 123, "name": "New Name"}
        result = src.server.update_project(123, '{"name": "New Name"}', session_id)
        mock_client.api.patch.assert_called_once_with("/projects/123", json={"name": "New Name"})
        assert result["name"] == "New Name"

    def test_update_project_no_kwargs(self, session_setup):
        """Test update_project with no kwargs returns current state."""
        session_id, mock_client = session_setup
        mock_client.api.projects.get.return_value = {"id": 123, "name": "Same", "version": 1}
        result = src.server.update_project(123, "{}", session_id)
        assert result["name"] == "Same"
        mock_client.api.projects.update.assert_not_called()

    def test_delete_project(self, session_setup):
        """Test delete_project."""
        session_id, mock_client = session_setup
        mock_client.api.projects.delete.return_value = None
        result = src.server.delete_project(123, session_id)
        assert result["status"] == "deleted"
        assert result["project_id"] == 123
        mock_client.api.projects.delete.assert_called_once_with(project_id=123)

    # ─── User Story tools tests ──────────────────────────────────────

    def test_list_user_stories(self, session_setup):
        """Test list_user_stories functionality"""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.list.return_value = [{"id": 456, "subject": "Test User Story"}]
        stories = src.server.list_user_stories(123, "{}", session_id)
        assert len(stories) == 1
        assert stories[0]["subject"] == "Test User Story"
        mock_client.api.user_stories.list.assert_called_once_with(project=123)

    def test_list_user_stories_with_filters(self, session_setup):
        """Test list_user_stories with filters."""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.list.return_value = [{"id": 1, "subject": "Filtered"}]
        src.server.list_user_stories(123, '{"status": 1}', session_id)
        mock_client.api.user_stories.list.assert_called_once_with(project=123, status=1)

    def test_create_user_story(self, session_setup):
        """Test create_user_story functionality"""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.create.return_value = {"id": 456, "subject": "New Story"}
        story = src.server.create_user_story(
            123, "New Story", '{"description": "Test description"}', session_id
        )
        assert story["subject"] == "New Story"
        assert story["id"] == 456
        mock_client.api.user_stories.create.assert_called_once_with(
            project=123, subject="New Story", description="Test description"
        )

    def test_create_user_story_empty_subject(self, session_setup):
        """Test create_user_story raises for empty subject."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="User story subject cannot be empty"):
            src.server.create_user_story(123, "", "{}", session_id)

    def test_get_user_story(self, session_setup):
        """Test get_user_story returns story by ID."""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.get.return_value = {
            "id": 456,
            "ref": 1,
            "subject": "Story",
            "status": 1,
            "project": 123,
            "version": 1,
        }
        result = src.server.get_user_story(456, session_id)
        assert result["id"] == 456
        mock_client.api.user_stories.get.assert_called_once_with(456)

    def test_update_user_story(self, session_setup):
        """Test update_user_story."""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.get.return_value = {
            "id": 456,
            "description": "Old desc",
            "version": 1,
        }
        mock_client.api.user_stories.edit.return_value = {
            "id": 456,
            "description": "New desc",
            "version": 2,
        }
        result = src.server.update_user_story(456, '{"description": "New desc"}', session_id)
        assert result["description"] == "New desc"
        mock_client.api.user_stories.edit.assert_called_once_with(
            user_story_id=456, version=1, description="New desc"
        )

    def test_update_user_story_no_kwargs(self, session_setup):
        """Test update_user_story with no kwargs returns current state."""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.get.return_value = {"id": 456, "subject": "Same", "version": 1}
        result = src.server.update_user_story(456, "{}", session_id)
        assert result["subject"] == "Same"
        mock_client.api.user_stories.edit.assert_not_called()

    def test_delete_user_story(self, session_setup):
        """Test delete_user_story."""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.delete.return_value = None
        result = src.server.delete_user_story(456, session_id)
        assert result["status"] == "deleted"
        assert result["user_story_id"] == 456

    def test_assign_user_story_to_user(self, session_setup):
        """Test assign_user_story_to_user delegates to update."""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.get.return_value = {
            "id": 456,
            "assigned_to": None,
            "version": 1,
        }
        mock_client.api.user_stories.edit.return_value = {
            "id": 456,
            "assigned_to": 10,
            "version": 2,
        }
        src.server.assign_user_story_to_user(456, 10, session_id)
        mock_client.api.user_stories.edit.assert_called_once_with(
            user_story_id=456, version=1, assigned_to=10
        )

    def test_unassign_user_story_from_user(self, session_setup):
        """Test unassign_user_story_from_user sets assigned_to to None."""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.get.return_value = {"id": 456, "assigned_to": 10, "version": 1}
        mock_client.api.user_stories.edit.return_value = {
            "id": 456,
            "assigned_to": None,
            "version": 2,
        }
        src.server.unassign_user_story_from_user(456, session_id)
        mock_client.api.user_stories.edit.assert_called_once_with(
            user_story_id=456, version=1, assigned_to=None
        )

    def test_get_user_story_statuses(self, session_setup):
        """Test get_user_story_statuses."""
        session_id, mock_client = session_setup
        mock_client.api.userstory_statuses.list.return_value = [
            {"id": 1, "name": "New"},
            {"id": 2, "name": "In Progress"},
        ]
        result = src.server.get_user_story_statuses(123, session_id)
        assert len(result) == 2
        mock_client.api.userstory_statuses.list.assert_called_once_with(
            query_params={"project": 123}
        )

    # ─── Task tools tests ────────────────────────────────────────────

    def test_list_tasks(self, session_setup):
        """Test list_tasks functionality"""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = [{"id": 789, "subject": "Test Task"}]
        tasks = src.server.list_tasks(123, "{}", session_id)
        assert len(tasks) == 1
        assert tasks[0]["subject"] == "Test Task"
        mock_client.api.get.assert_called_once_with("/tasks", params={"project": 123})

    def test_list_tasks_with_filters(self, session_setup):
        """Test list_tasks with filters."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = [{"id": 1, "subject": "Filtered"}]
        src.server.list_tasks(123, '{"milestone": 5}', session_id)
        mock_client.api.get.assert_called_once_with(
            "/tasks", params={"project": 123, "milestone": 5}
        )

    def test_create_task(self, session_setup):
        """Test create_task."""
        session_id, mock_client = session_setup
        mock_client.api.tasks.create.return_value = {
            "id": 789,
            "subject": "New Task",
            "project": 123,
        }
        result = src.server.create_task(123, "New Task", "{}", session_id)
        assert result["id"] == 789
        assert result["subject"] == "New Task"
        mock_client.api.tasks.create.assert_called_once_with(
            project=123, subject="New Task", data=None
        )

    def test_create_task_with_kwargs(self, session_setup):
        """Test create_task with extra kwargs."""
        session_id, mock_client = session_setup
        mock_client.api.tasks.create.return_value = {"id": 789, "subject": "Task"}
        src.server.create_task(123, "Task", '{"description": "Some desc"}', session_id)
        mock_client.api.tasks.create.assert_called_once_with(
            project=123, subject="Task", data={"description": "Some desc"}
        )

    def test_create_task_empty_subject(self, session_setup):
        """Test create_task raises for empty subject."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Task subject cannot be empty"):
            src.server.create_task(123, "", "{}", session_id)

    def test_get_task(self, session_setup):
        """Test get_task returns task by ID."""
        session_id, mock_client = session_setup
        mock_client.api.tasks.get.return_value = {
            "id": 789,
            "ref": 5,
            "subject": "Task",
            "status": 1,
            "project": 123,
            "version": 1,
        }
        result = src.server.get_task(789, session_id)
        assert result["id"] == 789
        mock_client.api.tasks.get.assert_called_once_with(789)

    def test_update_task(self, session_setup):
        """Test update_task."""
        session_id, mock_client = session_setup
        mock_client.api.tasks.get.return_value = {"id": 789, "description": "Old", "version": 1}
        mock_client.api.tasks.edit.return_value = {"id": 789, "description": "New", "version": 2}
        result = src.server.update_task(789, '{"description": "New"}', session_id)
        assert result["description"] == "New"
        mock_client.api.tasks.edit.assert_called_once_with(
            task_id=789, version=1, data={"description": "New"}
        )

    def test_update_task_no_kwargs(self, session_setup):
        """Test update_task with no kwargs returns current state."""
        session_id, mock_client = session_setup
        mock_client.api.tasks.get.return_value = {"id": 789, "subject": "Same", "version": 1}
        result = src.server.update_task(789, "{}", session_id)
        assert result["subject"] == "Same"
        mock_client.api.tasks.edit.assert_not_called()

    def test_delete_task(self, session_setup):
        """Test delete_task."""
        session_id, mock_client = session_setup
        mock_client.api.tasks.delete.return_value = None
        result = src.server.delete_task(789, session_id)
        assert result["status"] == "deleted"
        assert result["task_id"] == 789

    def test_assign_task_to_user(self, session_setup):
        """Test assign_task_to_user delegates to update_task."""
        session_id, mock_client = session_setup
        mock_client.api.tasks.get.return_value = {"id": 789, "version": 1}
        mock_client.api.tasks.edit.return_value = {"id": 789, "assigned_to": 10, "version": 2}
        src.server.assign_task_to_user(789, 10, session_id)
        mock_client.api.tasks.edit.assert_called_once_with(
            task_id=789, version=1, data={"assigned_to": 10}
        )

    def test_unassign_task_from_user(self, session_setup):
        """Test unassign_task_from_user sets assigned_to to None."""
        session_id, mock_client = session_setup
        mock_client.api.tasks.get.return_value = {"id": 789, "version": 1}
        mock_client.api.tasks.edit.return_value = {"id": 789, "assigned_to": None, "version": 2}
        src.server.unassign_task_from_user(789, session_id)
        mock_client.api.tasks.edit.assert_called_once_with(
            task_id=789, version=1, data={"assigned_to": None}
        )

    # ─── Issue tools tests ───────────────────────────────────────────

    def test_list_issues(self, session_setup):
        """Test list_issues."""
        session_id, mock_client = session_setup
        mock_client.api.issues.list.return_value = [{"id": 100, "subject": "Bug"}]
        result = src.server.list_issues(123, "{}", session_id)
        assert len(result) == 1
        assert result[0]["subject"] == "Bug"
        mock_client.api.issues.list.assert_called_once_with(query_params={"project": 123})

    def test_list_issues_with_filters(self, session_setup):
        """Test list_issues with filters."""
        session_id, mock_client = session_setup
        mock_client.api.issues.list.return_value = []
        src.server.list_issues(123, '{"priority": 3}', session_id)
        mock_client.api.issues.list.assert_called_once_with(
            query_params={"project": 123, "priority": 3}
        )

    def test_create_issue(self, session_setup):
        """Test create_issue."""
        session_id, mock_client = session_setup
        mock_client.api.issues.create.return_value = {
            "id": 100,
            "subject": "New Bug",
            "project": 123,
        }
        result = src.server.create_issue(
            project_id=123,
            subject="New Bug",
            priority_id=1,
            status_id=1,
            severity_id=1,
            type_id=1,
            kwargs="{}",
            session_id=session_id,
        )
        assert result["id"] == 100
        assert result["subject"] == "New Bug"
        mock_client.api.issues.create.assert_called_once_with(
            project=123,
            subject="New Bug",
            data={"priority": 1, "status": 1, "type": 1, "severity": 1},
        )

    def test_create_issue_empty_subject(self, session_setup):
        """Test create_issue raises for empty subject."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Issue subject cannot be empty"):
            src.server.create_issue(123, "", 1, 1, 1, 1, "{}", session_id)

    def test_get_issue(self, session_setup):
        """Test get_issue returns issue by ID."""
        session_id, mock_client = session_setup
        mock_client.api.issues.get.return_value = {
            "id": 100,
            "ref": 10,
            "subject": "Bug",
            "status": 1,
            "priority": 1,
            "severity": 1,
            "project": 123,
            "version": 1,
        }
        result = src.server.get_issue(100, session_id)
        assert result["id"] == 100
        mock_client.api.issues.get.assert_called_once_with(100)

    def test_update_issue(self, session_setup):
        """Test update_issue."""
        session_id, mock_client = session_setup
        mock_client.api.issues.get.return_value = {"id": 100, "description": "Old", "version": 1}
        mock_client.api.issues.edit.return_value = {"id": 100, "description": "New", "version": 2}
        result = src.server.update_issue(100, '{"description": "New"}', session_id)
        assert result["description"] == "New"
        mock_client.api.issues.edit.assert_called_once_with(
            issue_id=100, version=1, data={"description": "New"}
        )

    def test_update_issue_no_kwargs(self, session_setup):
        """Test update_issue with no kwargs returns current state."""
        session_id, mock_client = session_setup
        mock_client.api.issues.get.return_value = {"id": 100, "subject": "Same", "version": 1}
        result = src.server.update_issue(100, "{}", session_id)
        assert result["subject"] == "Same"
        mock_client.api.issues.edit.assert_not_called()

    def test_delete_issue(self, session_setup):
        """Test delete_issue."""
        session_id, mock_client = session_setup
        mock_client.api.issues.delete.return_value = None
        result = src.server.delete_issue(100, session_id)
        assert result["status"] == "deleted"
        assert result["issue_id"] == 100

    def test_assign_issue_to_user(self, session_setup):
        """Test assign_issue_to_user delegates to update_issue."""
        session_id, mock_client = session_setup
        mock_client.api.issues.get.return_value = {"id": 100, "version": 1}
        mock_client.api.issues.edit.return_value = {"id": 100, "assigned_to": 10, "version": 2}
        src.server.assign_issue_to_user(100, 10, session_id)
        mock_client.api.issues.edit.assert_called_once_with(
            issue_id=100, version=1, data={"assigned_to": 10}
        )

    def test_unassign_issue_from_user(self, session_setup):
        """Test unassign_issue_from_user."""
        session_id, mock_client = session_setup
        mock_client.api.issues.get.return_value = {"id": 100, "version": 1}
        mock_client.api.issues.edit.return_value = {"id": 100, "assigned_to": None, "version": 2}
        src.server.unassign_issue_from_user(100, session_id)
        mock_client.api.issues.edit.assert_called_once_with(
            issue_id=100, version=1, data={"assigned_to": None}
        )

    def test_get_issue_statuses(self, session_setup):
        """Test get_issue_statuses."""
        session_id, mock_client = session_setup
        mock_client.api.issue_statuses.list.return_value = [
            {"id": 1, "name": "New"},
            {"id": 2, "name": "Closed"},
        ]
        result = src.server.get_issue_statuses(123, session_id)
        assert len(result) == 2
        mock_client.api.issue_statuses.list.assert_called_once_with(query_params={"project": 123})

    def test_get_issue_priorities(self, session_setup):
        """Test get_issue_priorities uses direct GET with /priorities endpoint."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = [
            {"id": 1, "name": "Low"},
            {"id": 2, "name": "Normal"},
            {"id": 3, "name": "High"},
        ]
        result = src.server.get_issue_priorities(123, session_id)
        assert len(result) == 3
        assert result[0]["name"] == "Low"
        # Verify it uses the direct GET call, not issue_priorities.list
        mock_client.api.get.assert_called_once_with("/priorities", params={"project": 123})

    def test_get_issue_severities(self, session_setup):
        """Test get_issue_severities uses direct GET with /severities endpoint."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = [
            {"id": 1, "name": "Wishlist"},
            {"id": 2, "name": "Minor"},
            {"id": 3, "name": "Normal"},
        ]
        result = src.server.get_issue_severities(123, session_id)
        assert len(result) == 3
        assert result[0]["name"] == "Wishlist"
        # Verify it uses the direct GET call, not issue_severities.list
        mock_client.api.get.assert_called_once_with("/severities", params={"project": 123})

    def test_get_issue_types(self, session_setup):
        """Test get_issue_types."""
        session_id, mock_client = session_setup
        mock_client.api.issue_types.list.return_value = [
            {"id": 1, "name": "Bug"},
            {"id": 2, "name": "Enhancement"},
        ]
        result = src.server.get_issue_types(123, session_id)
        assert len(result) == 2
        mock_client.api.issue_types.list.assert_called_once_with(query_params={"project": 123})

    # ─── Epic tools tests ────────────────────────────────────────────

    def test_list_epics(self, session_setup):
        """Test list_epics."""
        session_id, mock_client = session_setup
        mock_client.api.epics.list.return_value = [{"id": 200, "subject": "Epic 1"}]
        result = src.server.list_epics(123, "{}", session_id)
        assert len(result) == 1
        assert result[0]["subject"] == "Epic 1"
        mock_client.api.epics.list.assert_called_once_with(query_params={"project": 123})

    def test_list_epics_with_filters(self, session_setup):
        """Test list_epics with filters."""
        session_id, mock_client = session_setup
        mock_client.api.epics.list.return_value = []
        src.server.list_epics(123, '{"status": 2}', session_id)
        mock_client.api.epics.list.assert_called_once_with(
            query_params={"project": 123, "status": 2}
        )

    def test_create_epic(self, session_setup):
        """Test create_epic."""
        session_id, mock_client = session_setup
        mock_client.api.epics.create.return_value = {
            "id": 200,
            "subject": "New Epic",
            "project": 123,
        }
        result = src.server.create_epic(123, "New Epic", "{}", session_id)
        assert result["id"] == 200
        mock_client.api.epics.create.assert_called_once_with(project=123, subject="New Epic")

    def test_create_epic_with_kwargs(self, session_setup):
        """Test create_epic with extra kwargs."""
        session_id, mock_client = session_setup
        mock_client.api.epics.create.return_value = {"id": 200, "subject": "Epic"}
        src.server.create_epic(123, "Epic", '{"color": "#FF0000"}', session_id)
        mock_client.api.epics.create.assert_called_once_with(
            project=123, subject="Epic", color="#FF0000"
        )

    def test_create_epic_empty_subject(self, session_setup):
        """Test create_epic raises for empty subject."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Epic subject cannot be empty"):
            src.server.create_epic(123, "", "{}", session_id)

    def test_get_epic(self, session_setup):
        """Test get_epic returns epic by ID."""
        session_id, mock_client = session_setup
        mock_client.api.epics.get.return_value = {
            "id": 200,
            "ref": 1,
            "subject": "Epic",
            "status": 1,
            "project": 123,
            "version": 1,
        }
        result = src.server.get_epic(200, session_id)
        assert result["id"] == 200
        mock_client.api.epics.get.assert_called_once_with(200)

    def test_update_epic(self, session_setup):
        """Test update_epic."""
        session_id, mock_client = session_setup
        mock_client.api.epics.get.return_value = {"id": 200, "description": "Old", "version": 1}
        mock_client.api.epics.edit.return_value = {"id": 200, "description": "New", "version": 2}
        result = src.server.update_epic(200, '{"description": "New"}', session_id)
        assert result["description"] == "New"
        mock_client.api.epics.edit.assert_called_once_with(
            epic_id=200, version=1, description="New"
        )

    def test_update_epic_no_kwargs(self, session_setup):
        """Test update_epic with no kwargs returns current state."""
        session_id, mock_client = session_setup
        mock_client.api.epics.get.return_value = {"id": 200, "subject": "Same", "version": 1}
        result = src.server.update_epic(200, "{}", session_id)
        assert result["subject"] == "Same"
        mock_client.api.epics.edit.assert_not_called()

    def test_delete_epic(self, session_setup):
        """Test delete_epic."""
        session_id, mock_client = session_setup
        mock_client.api.epics.delete.return_value = None
        result = src.server.delete_epic(200, session_id)
        assert result["status"] == "deleted"
        assert result["epic_id"] == 200

    def test_assign_epic_to_user(self, session_setup):
        """Test assign_epic_to_user delegates to update_epic."""
        session_id, mock_client = session_setup
        mock_client.api.epics.get.return_value = {"id": 200, "version": 1}
        mock_client.api.epics.edit.return_value = {"id": 200, "assigned_to": 10, "version": 2}
        src.server.assign_epic_to_user(200, 10, session_id)
        mock_client.api.epics.edit.assert_called_once_with(epic_id=200, version=1, assigned_to=10)

    def test_unassign_epic_from_user(self, session_setup):
        """Test unassign_epic_from_user."""
        session_id, mock_client = session_setup
        mock_client.api.epics.get.return_value = {"id": 200, "version": 1}
        mock_client.api.epics.edit.return_value = {"id": 200, "assigned_to": None, "version": 2}
        src.server.unassign_epic_from_user(200, session_id)
        mock_client.api.epics.edit.assert_called_once_with(epic_id=200, version=1, assigned_to=None)

    # ─── Milestone tools tests ───────────────────────────────────────

    def test_list_milestones(self, session_setup):
        """Test list_milestones."""
        session_id, mock_client = session_setup
        mock_client.api.milestones.list.return_value = [
            {"id": 300, "name": "Sprint 1", "slug": "sprint-1", "project": 123}
        ]
        result = src.server.list_milestones(123, session_id)
        assert len(result) == 1
        assert result[0]["name"] == "Sprint 1"
        mock_client.api.milestones.list.assert_called_once_with(project=123)

    def test_create_milestone(self, session_setup):
        """Test create_milestone."""
        session_id, mock_client = session_setup
        mock_client.api.milestones.create.return_value = {
            "id": 300,
            "name": "Sprint 1",
            "project": 123,
        }
        result = src.server.create_milestone(
            123, "Sprint 1", "2025-01-01", "2025-01-14", session_id
        )
        assert result["id"] == 300
        mock_client.api.milestones.create.assert_called_once_with(
            project=123,
            name="Sprint 1",
            estimated_start="2025-01-01",
            estimated_finish="2025-01-14",
        )

    def test_create_milestone_missing_fields(self, session_setup):
        """Test create_milestone raises when required fields are missing."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Milestone requires"):
            src.server.create_milestone(123, "", "2025-01-01", "2025-01-14", session_id)

    def test_get_milestone(self, session_setup):
        """Test get_milestone."""
        session_id, mock_client = session_setup
        mock_client.api.milestones.get.return_value = {
            "id": 300,
            "name": "Sprint 1",
            "slug": "sprint-1",
            "project": 123,
            "version": 1,
        }
        result = src.server.get_milestone(300, session_id)
        assert result["id"] == 300
        mock_client.api.milestones.get.assert_called_once_with(300)

    def test_update_milestone(self, session_setup):
        """Test update_milestone."""
        session_id, mock_client = session_setup
        mock_client.api.milestones.get.return_value = {"id": 300, "name": "Sprint 1", "version": 1}
        mock_client.api.milestones.edit.return_value = {
            "id": 300,
            "name": "Sprint 1 Updated",
            "version": 2,
        }
        result = src.server.update_milestone(300, '{"name": "Sprint 1 Updated"}', session_id)
        assert result["name"] == "Sprint 1 Updated"
        mock_client.api.milestones.edit.assert_called_once_with(
            milestone_id=300, version=1, name="Sprint 1 Updated"
        )

    def test_update_milestone_no_kwargs(self, session_setup):
        """Test update_milestone with no kwargs returns current state."""
        session_id, mock_client = session_setup
        mock_client.api.milestones.get.return_value = {"id": 300, "name": "Sprint 1", "version": 1}
        result = src.server.update_milestone(300, "{}", session_id)
        assert result["name"] == "Sprint 1"
        mock_client.api.milestones.edit.assert_not_called()

    def test_delete_milestone(self, session_setup):
        """Test delete_milestone."""
        session_id, mock_client = session_setup
        mock_client.api.milestones.delete.return_value = None
        result = src.server.delete_milestone(300, session_id)
        assert result["status"] == "deleted"
        assert result["milestone_id"] == 300

    # ─── User management tools tests ─────────────────────────────────

    def test_get_project_members(self, session_setup):
        """Test get_project_members."""
        session_id, mock_client = session_setup
        mock_client.api.memberships.list.return_value = [
            {"id": 1, "user": 10, "full_name": "John Doe", "role_name": "Admin"}
        ]
        result = src.server.get_project_members(123, session_id)
        assert len(result) == 1
        assert result[0]["full_name"] == "John Doe"
        mock_client.api.memberships.list.assert_called_once_with(query_params={"project": 123})

    def test_invite_project_user(self, session_setup):
        """Test invite_project_user."""
        session_id, mock_client = session_setup
        mock_client.api.memberships.invite.return_value = {
            "id": 50,
            "email": "user@test.com",
            "role": 5,
        }
        result = src.server.invite_project_user(123, "user@test.com", 5, session_id)
        assert result["email"] == "user@test.com"
        mock_client.api.memberships.invite.assert_called_once_with(
            project=123, email="user@test.com", role_id=5
        )

    def test_invite_project_user_empty_email(self, session_setup):
        """Test invite_project_user raises for empty email."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Email cannot be empty"):
            src.server.invite_project_user(123, "", 5, session_id)

    # ─── Wiki tools tests ────────────────────────────────────────────

    def test_list_wiki_pages(self, session_setup):
        """Test list_wiki_pages."""
        session_id, mock_client = session_setup
        mock_client.api.wiki.list.return_value = [{"id": 400, "slug": "home", "project": 123}]
        result = src.server.list_wiki_pages(123, session_id)
        assert len(result) == 1
        assert result[0]["slug"] == "home"
        mock_client.api.wiki.list.assert_called_once_with(query_params={"project": 123})

    def test_get_wiki_page(self, session_setup):
        """Test get_wiki_page."""
        session_id, mock_client = session_setup
        mock_client.api.wiki.get.return_value = {
            "id": 400,
            "slug": "home",
            "content": "# Welcome",
            "project": 123,
            "version": 1,
        }
        result = src.server.get_wiki_page(400, session_id)
        assert result["id"] == 400
        assert result["slug"] == "home"
        mock_client.api.wiki.get.assert_called_once_with(400)

    # ─── Verbosity tests for various tools ───────────────────────────

    def test_list_projects_verbosity_minimal(self, session_setup):
        """Test list_projects with minimal verbosity."""
        session_id, mock_client = session_setup
        mock_client.api.projects.list.return_value = [
            {"id": 1, "name": "P1", "slug": "p1", "description": "Long desc", "version": 1}
        ]
        result = src.server.list_projects(session_id, verbosity="minimal")
        assert result == [{"id": 1, "name": "P1", "slug": "p1"}]

    def test_get_project_verbosity_full(self, session_setup):
        """Test get_project with full verbosity returns all fields."""
        session_id, mock_client = session_setup
        full_data = {"id": 1, "name": "P1", "extra": "value", "version": 1}
        mock_client.api.projects.get.return_value = full_data
        result = src.server.get_project(1, session_id, verbosity="full")
        assert result == full_data


# ─── Response Filtering tests ─────────────────────────────────────────


class TestResponseFiltering:
    """Tests for the response filtering functionality."""

    def test_filter_standard_always_includes_version(self):
        """version is required for updates in standard level."""
        for resource_type, levels in src.server.RESPONSE_FIELDS.items():
            if resource_type != "member":  # member doesn't have version
                assert "version" in levels["standard"], (
                    f"{resource_type} missing version in standard"
                )

    def test_filter_minimal_includes_id(self):
        """All minimal levels must include id."""
        for resource_type, levels in src.server.RESPONSE_FIELDS.items():
            assert "id" in levels["minimal"], f"{resource_type} missing id in minimal"

    def test_filter_minimal_includes_project_where_applicable(self):
        """Resources with project association must include project in minimal."""
        project_resources = ["user_story", "task", "issue", "epic", "milestone", "wiki_page"]
        for resource_type in project_resources:
            assert "project" in src.server.RESPONSE_FIELDS[resource_type]["minimal"], (
                f"{resource_type} missing project in minimal"
            )

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
        data = {
            "id": 1,
            "subject": "Test",
            "version": 1,
            "watchers": [1, 2],
            "extra_field": "value",
        }
        result = src.server._filter_response(data, "user_story", verbosity="full")
        assert result == data

    def test_filter_response_standard_filters_fields(self):
        """Standard verbosity should filter to defined fields."""
        data = {
            "id": 1,
            "ref": 123,
            "subject": "Test",
            "description": "Desc",
            "status": 1,
            "version": 2,
            "watchers": [1, 2],
            "extra_internal_field": "should_be_filtered",
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
            "id": 1,
            "ref": 123,
            "subject": "Test",
            "status": 1,
            "project": 10,
            "description": "Long description",
            "version": 2,
            "watchers": [1, 2],
        }
        result = src.server._filter_response(data, "user_story", verbosity="minimal")
        assert result == {"id": 1, "ref": 123, "subject": "Test", "status": 1, "project": 10}

    def test_filter_response_list_filters_each_item(self):
        """_filter_response should filter each item in a list."""
        data = [
            {"id": 1, "subject": "Story 1", "watchers": [1]},
            {"id": 2, "subject": "Story 2", "watchers": [2]},
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


# ─── Config tests ─────────────────────────────────────────────────────


class TestConfig:
    """Tests for the configuration module."""

    def test_mask_credential_normal(self):
        """Test masking a normal-length credential."""
        from src.config import mask_credential

        result = mask_credential("mysecretpassword")
        assert result.startswith("my")
        assert result.endswith("rd")
        assert "****" in result

    def test_mask_credential_short(self):
        """Test masking a short credential."""
        from src.config import mask_credential

        result = mask_credential("ab")
        assert result == "**"

    def test_mask_credential_empty(self):
        """Test masking an empty credential."""
        from src.config import mask_credential

        assert mask_credential("") == "<empty>"

    def test_taiga_settings_defaults(self):
        """Test TaigaSettings default values."""
        from src.config import TaigaSettings

        # Create with explicit values to avoid env pollution
        s = TaigaSettings(TAIGA_API_URL="http://test:9000")
        assert s.host == "http://test:9000"

    def test_taiga_settings_has_credentials_false(self):
        """Test has_credentials when no credentials set."""
        from src.config import TaigaSettings

        s = TaigaSettings(TAIGA_API_URL="http://test:9000")
        # If env vars are not set, credentials should be None
        if s.username is None and s.password is None:
            assert s.has_credentials is False


# ─── TaigaClientWrapper tests ────────────────────────────────────────


class TestTaigaClientWrapper:
    """Tests for the TaigaClientWrapper class."""

    def test_init_requires_host(self):
        """Test wrapper requires a host."""
        with pytest.raises(ValueError, match="Taiga host URL cannot be empty"):
            TaigaClientWrapper(host="")

    def test_init_sets_host(self):
        """Test wrapper stores the host."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        assert wrapper.host == "http://test:9000"
        assert wrapper.api is None

    def test_is_authenticated_false_initially(self):
        """Test wrapper is not authenticated initially."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        assert wrapper.is_authenticated is False

    def test_ensure_authenticated_raises(self):
        """Test _ensure_authenticated raises when not authenticated."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        with pytest.raises(PermissionError, match="Client not authenticated"):
            wrapper._ensure_authenticated()

    def test_list_resources_requires_auth(self):
        """Test list_resources raises when not authenticated."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        with pytest.raises(PermissionError):
            wrapper.list_resources("projects")

    def test_list_resources_raw_api(self):
        """Test list_resources uses raw API for tasks."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        wrapper.api = MagicMock()
        wrapper.api.auth_token = "test-token"
        wrapper.api.get.return_value = [{"id": 1}]
        result = wrapper.list_resources("tasks", project_id=123)
        wrapper.api.get.assert_called_once_with("/tasks", params={"project": 123})
        assert result == [{"id": 1}]

    def test_list_resources_project_kwarg(self):
        """Test list_resources uses project kwarg for user_stories."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        wrapper.api = MagicMock()
        wrapper.api.auth_token = "test-token"
        wrapper.api.user_stories.list.return_value = [{"id": 1}]
        result = wrapper.list_resources("user_stories", project_id=123)
        wrapper.api.user_stories.list.assert_called_once_with(project=123)
        assert result == [{"id": 1}]

    def test_list_resources_query_params(self):
        """Test list_resources uses query_params for issues."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        wrapper.api = MagicMock()
        wrapper.api.auth_token = "test-token"
        wrapper.api.issues.list.return_value = [{"id": 1}]
        result = wrapper.list_resources("issues", project_id=123)
        wrapper.api.issues.list.assert_called_once_with(query_params={"project": 123})
        assert result == [{"id": 1}]

    def test_list_resources_unknown_type(self):
        """Test list_resources raises for unknown resource type."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        wrapper.api = MagicMock()
        wrapper.api.auth_token = "test-token"
        wrapper.api.nonexistent = None
        with pytest.raises(ValueError, match="Unknown resource type"):
            wrapper.list_resources("nonexistent")
