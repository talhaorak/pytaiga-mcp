import json
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
        mock_client.list_resources.return_value = [{"id": 123, "name": "Test Project"}]
        projects = src.server.list_projects(session_id)
        assert len(projects) == 1
        assert projects[0]["name"] == "Test Project"
        assert projects[0]["id"] == 123
        mock_client.list_resources.assert_called_once_with("projects")

    def test_list_all_projects(self, session_setup):
        """Test list_all_projects delegates to list_projects."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [{"id": 1, "name": "P1"}]
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
        mock_client.api.projects.get_by_slug.return_value = {
            "id": 123,
            "name": "Test",
            "slug": "test-slug",
            "version": 1,
        }
        result = src.server.get_project_by_slug("test-slug", session_id)
        assert result["slug"] == "test-slug"
        mock_client.api.projects.get_by_slug.assert_called_once_with(slug="test-slug")

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
        mock_client.api.projects.edit.return_value = {"id": 123, "name": "New Name", "version": 2}
        result = src.server.update_project(123, '{"name": "New Name"}', session_id)
        mock_client.api.projects.edit.assert_called_once_with(
            project_id=123, version=1, name="New Name"
        )
        assert result["name"] == "New Name"

    def test_update_project_without_version(self, session_setup):
        """Test update_project when project has no version field (Taiga projects)."""
        session_id, mock_client = session_setup
        mock_client.api.projects.get.return_value = {"id": 123, "name": "Old Name"}
        mock_client.api.projects.edit.return_value = {"id": 123, "name": "New Name"}
        result = src.server.update_project(123, '{"name": "New Name"}', session_id)
        mock_client.api.projects.edit.assert_called_once_with(
            project_id=123, version=None, name="New Name"
        )
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

    # ─── Project Tag Management tests ─────────────────────────────────

    def test_get_project_tags_colors(self, session_setup):
        """Test get_project_tags_colors returns tag-color mapping."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = {"bug": "#FF0000", "feature": "#00FF00"}

        result = src.server.get_project_tags_colors(21, session_id)

        mock_client.api.get.assert_called_once_with("/projects/21/tags_colors")
        assert result == {"bug": "#FF0000", "feature": "#00FF00"}

    def test_edit_project_tag_rename(self, session_setup):
        """Test edit_project_tag renames a tag."""
        session_id, mock_client = session_setup
        mock_client.api.post.return_value = None

        result = src.server.edit_project_tag(
            21, "old-name", new_tag="new-name", session_id=session_id
        )

        mock_client.api.post.assert_called_once_with(
            "/projects/21/edit_tag", json={"tag": "old-name", "new_tag": "new-name"}
        )
        assert result["status"] == "tag_updated"
        assert result["new_tag"] == "new-name"

    def test_edit_project_tag_recolor(self, session_setup):
        """Test edit_project_tag changes tag color."""
        session_id, mock_client = session_setup
        mock_client.api.post.return_value = None

        result = src.server.edit_project_tag(21, "bug", color="#FF0000", session_id=session_id)

        mock_client.api.post.assert_called_once_with(
            "/projects/21/edit_tag", json={"tag": "bug", "color": "#FF0000"}
        )
        assert result["status"] == "tag_updated"
        assert result["color"] == "#FF0000"

    def test_edit_project_tag_empty_name_raises(self, session_setup):
        """Test edit_project_tag raises ValueError for empty tag name."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Tag name cannot be empty"):
            src.server.edit_project_tag(21, "", color="#FF0000", session_id=session_id)

    def test_edit_project_tag_rename_and_recolor(self, session_setup):
        """Test edit_project_tag with both color and new_tag."""
        session_id, mock_client = session_setup
        mock_client.api.post.return_value = None

        result = src.server.edit_project_tag(
            21, "bug", color="#0000FF", new_tag="defect", session_id=session_id
        )

        mock_client.api.post.assert_called_once_with(
            "/projects/21/edit_tag",
            json={"tag": "bug", "color": "#0000FF", "new_tag": "defect"},
        )
        assert result["status"] == "tag_updated"
        assert result["color"] == "#0000FF"
        assert result["new_tag"] == "defect"

    def test_edit_project_tag_no_changes_raises(self, session_setup):
        """Test edit_project_tag raises ValueError when neither color nor new_tag provided."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="At least one of"):
            src.server.edit_project_tag(21, "bug", session_id=session_id)

    def test_mix_project_tags(self, session_setup):
        """Test mix_project_tags merges tags."""
        session_id, mock_client = session_setup
        mock_client.api.post.return_value = None

        result = src.server.mix_project_tags(21, ["bug", "defect"], "bug", session_id)

        mock_client.api.post.assert_called_once_with(
            "/projects/21/mix_tags", json={"from_tags": ["bug", "defect"], "to_tag": "bug"}
        )
        assert result["status"] == "tags_merged"
        assert result["from_tags"] == ["bug", "defect"]
        assert result["to_tag"] == "bug"

    def test_mix_project_tags_empty_to_tag_raises(self, session_setup):
        """Test mix_project_tags raises ValueError for empty target tag."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Target tag name"):
            src.server.mix_project_tags(21, ["bug"], "", session_id)

    def test_mix_project_tags_empty_from_tags_raises(self, session_setup):
        """Test mix_project_tags raises ValueError for empty from_tags list."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="from_tags"):
            src.server.mix_project_tags(21, [], "bug", session_id)

    def test_mix_project_tags_strips_whitespace(self, session_setup):
        """Test mix_project_tags strips whitespace from tag names."""
        session_id, mock_client = session_setup
        mock_client.api.post.return_value = None

        src.server.mix_project_tags(21, ["  bug  ", "defect", "  "], "  merged  ", session_id)

        mock_client.api.post.assert_called_once_with(
            "/projects/21/mix_tags", json={"from_tags": ["bug", "defect"], "to_tag": "merged"}
        )

    # ─── User Story tools tests ──────────────────────────────────────

    def test_list_user_stories(self, session_setup):
        """Test list_user_stories functionality"""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [{"id": 456, "subject": "Test User Story"}]
        stories = src.server.list_user_stories(123, "{}", session_id)
        assert len(stories) == 1
        assert stories[0]["subject"] == "Test User Story"
        mock_client.list_resources.assert_called_once_with("user_stories", project_id=123)

    def test_list_user_stories_with_filters(self, session_setup):
        """Test list_user_stories with filters."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [{"id": 1, "subject": "Filtered"}]
        src.server.list_user_stories(123, '{"status": 1}', session_id)
        mock_client.list_resources.assert_called_once_with("user_stories", project_id=123, status=1)

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

    def test_get_user_story_by_ref(self, session_setup):
        """Test get_user_story_by_ref returns story by ref number."""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.get_by_ref.return_value = {
            "id": 456,
            "ref": 1,
            "subject": "Story",
            "status": 1,
            "project": 123,
            "version": 1,
        }
        result = src.server.get_user_story_by_ref(123, 1, session_id)
        assert result["id"] == 456
        assert result["ref"] == 1
        mock_client.api.user_stories.get_by_ref.assert_called_once_with(ref=1, project=123)

    def test_get_user_story_by_ref_not_found(self, session_setup):
        """Test get_user_story_by_ref raises when ref not found."""
        session_id, mock_client = session_setup
        mock_client.api.user_stories.get_by_ref.return_value = None
        with pytest.raises(ValueError, match="not found"):
            src.server.get_user_story_by_ref(123, 999, session_id)

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
        mock_client.list_resources.return_value = [
            {"id": 1, "name": "New"},
            {"id": 2, "name": "In Progress"},
        ]
        result = src.server.get_user_story_statuses(123, session_id)
        assert len(result) == 2
        mock_client.list_resources.assert_called_once_with("userstory_statuses", project_id=123)

    # ─── Task tools tests ────────────────────────────────────────────

    def test_list_tasks(self, session_setup):
        """Test list_tasks functionality"""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [{"id": 789, "subject": "Test Task"}]
        tasks = src.server.list_tasks(123, "{}", session_id)
        assert len(tasks) == 1
        assert tasks[0]["subject"] == "Test Task"
        mock_client.list_resources.assert_called_once_with("tasks", project_id=123)

    def test_list_tasks_with_filters(self, session_setup):
        """Test list_tasks with filters."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [{"id": 1, "subject": "Filtered"}]
        src.server.list_tasks(123, '{"milestone": 5}', session_id)
        mock_client.list_resources.assert_called_once_with("tasks", project_id=123, milestone=5)

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

    def test_get_task_by_ref(self, session_setup):
        """Test get_task_by_ref returns task by ref number via direct API call."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = {
            "id": 789,
            "ref": 5,
            "subject": "Task",
            "status": 1,
            "project": 123,
            "version": 1,
        }
        result = src.server.get_task_by_ref(123, 5, session_id)
        assert result["id"] == 789
        assert result["ref"] == 5
        mock_client.api.get.assert_called_once_with(
            "/tasks/by_ref", params={"ref": 5, "project": 123}
        )

    def test_get_task_by_ref_not_found(self, session_setup):
        """Test get_task_by_ref raises when ref not found."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = None
        with pytest.raises(ValueError, match="not found"):
            src.server.get_task_by_ref(123, 999, session_id)

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
        mock_client.list_resources.return_value = [{"id": 100, "subject": "Bug"}]
        result = src.server.list_issues(123, "{}", session_id)
        assert len(result) == 1
        assert result[0]["subject"] == "Bug"
        mock_client.list_resources.assert_called_once_with("issues", project_id=123)

    def test_list_issues_with_filters(self, session_setup):
        """Test list_issues with filters."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = []
        src.server.list_issues(123, '{"priority": 3}', session_id)
        mock_client.list_resources.assert_called_once_with("issues", project_id=123, priority=3)

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

    def test_get_issue_by_ref(self, session_setup):
        """Test get_issue_by_ref returns issue by ref number."""
        session_id, mock_client = session_setup
        mock_client.api.issues.get_by_ref.return_value = {
            "id": 100,
            "ref": 10,
            "subject": "Bug",
            "status": 1,
            "priority": 1,
            "severity": 1,
            "project": 123,
            "version": 1,
        }
        result = src.server.get_issue_by_ref(123, 10, session_id)
        assert result["id"] == 100
        assert result["ref"] == 10
        mock_client.api.issues.get_by_ref.assert_called_once_with(ref=10, project=123)

    def test_get_issue_by_ref_not_found(self, session_setup):
        """Test get_issue_by_ref raises when ref not found."""
        session_id, mock_client = session_setup
        mock_client.api.issues.get_by_ref.return_value = {}
        with pytest.raises(ValueError, match="not found"):
            src.server.get_issue_by_ref(123, 999, session_id)

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
        mock_client.list_resources.return_value = [
            {"id": 1, "name": "New"},
            {"id": 2, "name": "Closed"},
        ]
        result = src.server.get_issue_statuses(123, session_id)
        assert len(result) == 2
        mock_client.list_resources.assert_called_once_with("issue_statuses", project_id=123)

    def test_get_issue_priorities(self, session_setup):
        """Test get_issue_priorities."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [
            {"id": 1, "name": "Low"},
            {"id": 2, "name": "Normal"},
            {"id": 3, "name": "High"},
        ]
        result = src.server.get_issue_priorities(123, session_id)
        assert len(result) == 3
        assert result[0]["name"] == "Low"
        mock_client.list_resources.assert_called_once_with("priorities", project_id=123)

    def test_get_issue_severities(self, session_setup):
        """Test get_issue_severities."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [
            {"id": 1, "name": "Wishlist"},
            {"id": 2, "name": "Minor"},
            {"id": 3, "name": "Normal"},
        ]
        result = src.server.get_issue_severities(123, session_id)
        assert len(result) == 3
        assert result[0]["name"] == "Wishlist"
        mock_client.list_resources.assert_called_once_with("severities", project_id=123)

    def test_get_issue_types(self, session_setup):
        """Test get_issue_types."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [
            {"id": 1, "name": "Bug"},
            {"id": 2, "name": "Enhancement"},
        ]
        result = src.server.get_issue_types(123, session_id)
        assert len(result) == 2
        mock_client.list_resources.assert_called_once_with("issue_types", project_id=123)

    # ─── Epic tools tests ────────────────────────────────────────────

    def test_list_epics(self, session_setup):
        """Test list_epics."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [{"id": 200, "subject": "Epic 1"}]
        result = src.server.list_epics(123, "{}", session_id)
        assert len(result) == 1
        assert result[0]["subject"] == "Epic 1"
        mock_client.list_resources.assert_called_once_with("epics", project_id=123)

    def test_list_epics_with_filters(self, session_setup):
        """Test list_epics with filters."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = []
        src.server.list_epics(123, '{"status": 2}', session_id)
        mock_client.list_resources.assert_called_once_with("epics", project_id=123, status=2)

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

    def test_get_epic_by_ref(self, session_setup):
        """Test get_epic_by_ref returns epic by ref number."""
        session_id, mock_client = session_setup
        mock_client.api.epics.get_by_ref.return_value = {
            "id": 200,
            "ref": 1,
            "subject": "Epic",
            "status": 1,
            "project": 123,
            "version": 1,
        }
        result = src.server.get_epic_by_ref(123, 1, session_id)
        assert result["id"] == 200
        assert result["ref"] == 1
        mock_client.api.epics.get_by_ref.assert_called_once_with(ref=1, project=123)

    def test_get_epic_by_ref_not_found(self, session_setup):
        """Test get_epic_by_ref raises when ref not found."""
        session_id, mock_client = session_setup
        mock_client.api.epics.get_by_ref.return_value = {}
        with pytest.raises(ValueError, match="not found"):
            src.server.get_epic_by_ref(123, 999, session_id)

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
        mock_client.list_resources.return_value = [
            {"id": 300, "name": "Sprint 1", "slug": "sprint-1", "project": 123}
        ]
        result = src.server.list_milestones(123, session_id)
        assert len(result) == 1
        assert result[0]["name"] == "Sprint 1"
        mock_client.list_resources.assert_called_once_with("milestones", project_id=123)

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
        mock_client.list_resources.return_value = [
            {"id": 1, "user": 10, "full_name": "John Doe", "role_name": "Admin"}
        ]
        result = src.server.get_project_members(123, session_id)
        assert len(result) == 1
        assert result[0]["full_name"] == "John Doe"
        mock_client.list_resources.assert_called_once_with("memberships", project_id=123)

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
        mock_client.list_resources.return_value = [{"id": 400, "slug": "home", "project": 123}]
        result = src.server.list_wiki_pages(123, session_id)
        assert len(result) == 1
        assert result[0]["slug"] == "home"
        mock_client.list_resources.assert_called_once_with("wiki", project_id=123)

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

    def test_get_wiki_page_by_slug(self, session_setup):
        """Test get_wiki_page_by_slug."""
        session_id, mock_client = session_setup
        mock_client.api.wiki.get_by_slug.return_value = {
            "id": 400,
            "slug": "home",
            "content": "# Welcome",
            "project": 123,
            "version": 1,
        }
        result = src.server.get_wiki_page_by_slug(123, "home", session_id)
        assert result["id"] == 400
        assert result["slug"] == "home"
        mock_client.api.wiki.get_by_slug.assert_called_once_with(slug="home", project=123)

    def test_get_wiki_page_by_slug_not_found(self, session_setup):
        """Test get_wiki_page_by_slug raises ValueError when not found."""
        session_id, mock_client = session_setup
        mock_client.api.wiki.get_by_slug.return_value = {}
        with pytest.raises(ValueError, match="not found"):
            src.server.get_wiki_page_by_slug(123, "nonexistent", session_id)

    def test_update_wiki_page(self, session_setup):
        """Test update_wiki_page."""
        session_id, mock_client = session_setup
        mock_client.api.wiki.get.return_value = {
            "id": 400,
            "slug": "home",
            "content": "# Welcome",
            "project": 123,
            "version": 1,
        }
        mock_client.api.wiki.edit.return_value = {
            "id": 400,
            "slug": "home",
            "content": "# Updated",
            "project": 123,
            "version": 2,
        }
        result = src.server.update_wiki_page(400, json.dumps({"content": "# Updated"}), session_id)
        assert result["content"] == "# Updated"
        assert result["version"] == 2
        mock_client.api.wiki.edit.assert_called_once_with(
            wiki_page_id=400, version=1, data={"content": "# Updated"}
        )

    def test_update_wiki_page_no_kwargs(self, session_setup):
        """Test update_wiki_page with no kwargs returns current state."""
        session_id, mock_client = session_setup
        mock_client.api.wiki.get.return_value = {
            "id": 400,
            "slug": "home",
            "content": "# Welcome",
            "project": 123,
            "version": 1,
        }
        result = src.server.update_wiki_page(400, None, session_id)
        assert result["id"] == 400
        mock_client.api.wiki.edit.assert_not_called()

    def test_delete_wiki_page(self, session_setup):
        """Test delete_wiki_page."""
        session_id, mock_client = session_setup
        mock_client.api.wiki.delete.return_value = None
        result = src.server.delete_wiki_page(400, session_id)
        assert result["status"] == "deleted"
        assert result["wiki_page_id"] == 400
        mock_client.api.wiki.delete.assert_called_once_with(wiki_page_id=400)

    # ─── Verbosity tests for various tools ───────────────────────────

    def test_list_projects_verbosity_minimal(self, session_setup):
        """Test list_projects with minimal verbosity."""
        session_id, mock_client = session_setup
        mock_client.list_resources.return_value = [
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

    # ─── Comment tests ─────────────────────────────────────────────────

    def test_add_comment(self, session_setup):
        """Test add_comment on an issue."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = {"id": 42, "version": 3}
        mock_client.api.patch.return_value = {"id": 42, "version": 4}

        result = src.server.add_comment(42, "issue", "Test comment", session_id)

        mock_client.api.get.assert_called_once_with("/issues/42")
        mock_client.api.patch.assert_called_once_with(
            "/issues/42", json={"comment": "Test comment", "version": 3}
        )
        assert result == {
            "status": "comment_added",
            "object_type": "issue",
            "object_id": 42,
        }

    def test_add_comment_user_story(self, session_setup):
        """Test add_comment with user_story alias uses /userstories/ path."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = {"id": 10, "version": 1}
        mock_client.api.patch.return_value = {"id": 10, "version": 2}

        result = src.server.add_comment(10, "user_story", "A comment", session_id)

        mock_client.api.get.assert_called_once_with("/userstories/10")
        mock_client.api.patch.assert_called_once_with(
            "/userstories/10", json={"comment": "A comment", "version": 1}
        )
        assert result["status"] == "comment_added"

    def test_add_comment_invalid_type(self, session_setup):
        """Test add_comment raises ValueError for invalid object_type."""
        session_id, mock_client = session_setup
        with pytest.raises(ValueError, match="Invalid object_type"):
            src.server.add_comment(1, "invalid_type", "comment", session_id)

    def test_add_comment_missing_version(self, session_setup):
        """Test add_comment raises ValueError when object has no version field."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = {"id": 42}

        with pytest.raises(RuntimeError, match="Server error"):
            src.server.add_comment(42, "issue", "Test comment", session_id)

    def test_list_comments(self, session_setup):
        """Test list_comments filters history to non-empty comments."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = [
            {
                "id": "abc",
                "comment": "First comment",
                "comment_html": "<p>First comment</p>",
                "user": {"id": 1, "name": "User1"},
                "created_at": "2026-01-01T00:00:00Z",
                "delete_comment_date": None,
            },
            {
                "id": "def",
                "comment": "",
                "user": {"id": 1, "name": "User1"},
                "created_at": "2026-01-02T00:00:00Z",
            },
            {
                "id": "mno",
                "comment": "   ",
                "user": {"id": 1, "name": "User1"},
                "created_at": "2026-01-02T01:00:00Z",
            },
            {
                "id": "ghi",
                "comment": "Second comment",
                "comment_html": "<p>Second comment</p>",
                "user": {"id": 2, "name": "User2"},
                "created_at": "2026-01-03T00:00:00Z",
                "delete_comment_date": None,
            },
            {
                "id": "jkl",
                "comment": "Deleted comment",
                "comment_html": "<p>Deleted comment</p>",
                "user": {"id": 1, "name": "User1"},
                "created_at": "2026-01-04T00:00:00Z",
                "delete_comment_date": "2026-01-04T01:00:00Z",
            },
        ]

        result = src.server.list_comments(42, "issue", session_id)

        mock_client.api.get.assert_called_once_with("/history/issue/42")
        assert len(result) == 2
        assert result[0]["comment"] == "First comment"
        assert result[1]["comment"] == "Second comment"
        assert "delete_comment_date" not in result[0]

    def test_list_comments_userstory_alias(self, session_setup):
        """Test list_comments with 'userstory' input uses /history/userstory/ path."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = []

        src.server.list_comments(5, "userstory", session_id)

        mock_client.api.get.assert_called_once_with("/history/userstory/5")

    def test_list_comments_invalid_type(self, session_setup):
        """Test list_comments raises ValueError for invalid object_type."""
        session_id, mock_client = session_setup
        with pytest.raises(ValueError, match="Invalid object_type"):
            src.server.list_comments(1, "invalid_type", session_id)

    def test_list_comments_empty_history(self, session_setup):
        """Test list_comments returns empty list for empty history."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = []

        result = src.server.list_comments(1, "task", session_id)

        assert result == []

    # ─── Comment Management tests ──────────────────────────────────────

    def test_edit_comment(self, session_setup):
        """Test edit_comment posts to the correct history endpoint."""
        session_id, mock_client = session_setup
        mock_client.api.post.return_value = None

        result = src.server.edit_comment(42, "issue", "abc123", "Updated text", session_id)

        mock_client.api.post.assert_called_once_with(
            "/history/issue/42/edit_comment",
            json={"comment_id": "abc123", "comment": "Updated text"},
        )
        assert result["status"] == "comment_edited"
        assert result["comment_id"] == "abc123"

    def test_edit_comment_strips_text(self, session_setup):
        """Test edit_comment strips whitespace from new comment text."""
        session_id, mock_client = session_setup
        mock_client.api.post.return_value = None

        src.server.edit_comment(42, "task", "abc", "  trimmed  ", session_id)

        mock_client.api.post.assert_called_once_with(
            "/history/task/42/edit_comment",
            json={"comment_id": "abc", "comment": "trimmed"},
        )

    def test_edit_comment_empty_text_raises(self, session_setup):
        """Test edit_comment raises ValueError for empty new comment."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="New comment text must not be empty"):
            src.server.edit_comment(42, "issue", "abc", "", session_id)

    def test_edit_comment_invalid_type_raises(self, session_setup):
        """Test edit_comment raises ValueError for invalid object_type."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Invalid object_type"):
            src.server.edit_comment(42, "invalid", "abc", "text", session_id)

    def test_delete_comment(self, session_setup):
        """Test delete_comment posts to the correct history endpoint."""
        session_id, mock_client = session_setup
        mock_client.api.post.return_value = None

        result = src.server.delete_comment(42, "user_story", "abc123", session_id)

        mock_client.api.post.assert_called_once_with(
            "/history/userstory/42/delete_comment",
            json={"comment_id": "abc123"},
        )
        assert result["status"] == "comment_deleted"
        assert result["comment_id"] == "abc123"

    def test_delete_comment_empty_id_raises(self, session_setup):
        """Test delete_comment raises ValueError for empty comment_id."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Comment ID must not be empty"):
            src.server.delete_comment(42, "issue", "", session_id)

    def test_undelete_comment(self, session_setup):
        """Test undelete_comment posts to the correct history endpoint."""
        session_id, mock_client = session_setup
        mock_client.api.post.return_value = None

        result = src.server.undelete_comment(42, "epic", "abc123", session_id)

        mock_client.api.post.assert_called_once_with(
            "/history/epic/42/undelete_comment",
            json={"comment_id": "abc123"},
        )
        assert result["status"] == "comment_restored"
        assert result["comment_id"] == "abc123"

    def test_undelete_comment_invalid_type_raises(self, session_setup):
        """Test undelete_comment raises ValueError for invalid object_type."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Invalid object_type"):
            src.server.undelete_comment(42, "wiki", "abc", session_id)

    def test_get_comment_versions(self, session_setup):
        """Test get_comment_versions returns version history."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = [
            {"date": "2026-01-01T00:00:00Z", "comment": "v1"},
            {"date": "2026-01-02T00:00:00Z", "comment": "v2"},
        ]

        result = src.server.get_comment_versions(42, "task", "abc123", session_id)

        mock_client.api.get.assert_called_once_with("/history/task/42/comment_versions/abc123")
        assert result["comment_id"] == "abc123"
        assert len(result["versions"]) == 2

    def test_get_comment_versions_empty_id_raises(self, session_setup):
        """Test get_comment_versions raises ValueError for empty comment_id."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Comment ID must not be empty"):
            src.server.get_comment_versions(42, "issue", "", session_id)

    # ─── History / Audit Trail tests ───────────────────────────────────

    def test_get_history(self, session_setup):
        """Test get_history returns full change history."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = [
            {"id": "a", "type": 1, "values_diff": {"status": ["New", "In progress"]}},
            {"id": "b", "type": 1, "comment": "Some comment"},
        ]

        result = src.server.get_history(42, "issue", session_id)

        mock_client.api.get.assert_called_once_with("/history/issue/42")
        assert result["object_type"] == "issue"
        assert result["object_id"] == 42
        assert len(result["history"]) == 2

    def test_get_history_wiki(self, session_setup):
        """Test get_history works with wiki type."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = []

        result = src.server.get_history(10, "wiki", session_id)

        mock_client.api.get.assert_called_once_with("/history/wiki/10")
        assert result["history"] == []

    def test_get_history_wiki_page_alias(self, session_setup):
        """Test get_history maps wiki_page to wiki path."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = []

        src.server.get_history(10, "wiki_page", session_id)

        mock_client.api.get.assert_called_once_with("/history/wiki/10")

    def test_get_history_user_story(self, session_setup):
        """Test get_history maps user_story to userstory path."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = [{"id": "x"}]

        result = src.server.get_history(5, "user_story", session_id)

        mock_client.api.get.assert_called_once_with("/history/userstory/5")
        assert len(result["history"]) == 1

    def test_get_history_invalid_type_raises(self, session_setup):
        """Test get_history raises ValueError for invalid object_type."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Invalid object_type"):
            src.server.get_history(42, "project", session_id)

    def test_get_history_no_session_raises(self):
        """Test get_history raises ValueError when no session available."""
        src.server.active_sessions.clear()
        with pytest.raises(ValueError, match="No session_id provided"):
            src.server.get_history(42, "issue")

    # ─── Login default session tests (PR: fix/login-default-session-and-slug) ──

    def test_login_sets_default_session_when_none_exists(self):
        """Test that login() sets the default session when no default exists."""
        with patch.object(TaigaClientWrapper, "login", return_value=True):
            src.server.active_sessions.clear()
            result = src.server.login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)
            assert "session_id" in result
            # Default session should have been set
            assert src.server.DEFAULT_SESSION_ID in src.server.active_sessions
            # The default session wrapper should be the same object as the new session's
            new_session_wrapper = src.server.active_sessions[result["session_id"]]
            default_wrapper = src.server.active_sessions[src.server.DEFAULT_SESSION_ID]
            assert new_session_wrapper is default_wrapper
            src.server.active_sessions.clear()

    def test_login_does_not_overwrite_existing_default_session(self):
        """Test that login() does NOT overwrite an existing default session."""
        existing_default = MagicMock()
        existing_default.is_authenticated = True
        src.server.active_sessions.clear()
        src.server.active_sessions[src.server.DEFAULT_SESSION_ID] = existing_default

        with patch.object(TaigaClientWrapper, "login", return_value=True):
            result = src.server.login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)
            assert "session_id" in result
            # Default session should still be the original one
            assert src.server.active_sessions[src.server.DEFAULT_SESSION_ID] is existing_default
            src.server.active_sessions.clear()

    # ─── Search tests ──────────────────────────────────────────────────

    def test_search_project(self, session_setup):
        """Test search_project returns structured results from Taiga search API."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = {
            "count": 3,
            "userstories": [{"id": 1, "ref": 10, "subject": "US match"}],
            "tasks": [{"id": 2, "ref": 20, "subject": "Task match"}],
            "issues": [{"id": 3, "ref": 30, "subject": "Issue match"}],
            "wikipages": [],
            "epics": [],
        }

        result = src.server.search_project(21, "match", session_id)

        mock_client.api.get.assert_called_once_with(
            "/search", params={"project": 21, "text": "match"}
        )
        assert result["count"] == 3
        assert len(result["userstories"]) == 1
        assert len(result["tasks"]) == 1
        assert len(result["issues"]) == 1
        assert result["wikipages"] == []
        assert result["epics"] == []

    def test_search_project_empty_text_raises(self, session_setup):
        """Test search_project raises ValueError for empty search text."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Search text cannot be empty"):
            src.server.search_project(21, "", session_id)

    def test_search_project_whitespace_text_raises(self, session_setup):
        """Test search_project raises ValueError for whitespace-only search text."""
        session_id, _ = session_setup
        with pytest.raises(ValueError, match="Search text cannot be empty"):
            src.server.search_project(21, "   ", session_id)

    def test_search_project_strips_text(self, session_setup):
        """Test search_project strips whitespace from search text."""
        session_id, mock_client = session_setup
        mock_client.api.get.return_value = {
            "count": 0,
            "userstories": [],
            "tasks": [],
            "issues": [],
            "wikipages": [],
            "epics": [],
        }

        src.server.search_project(21, "  hello  ", session_id)

        mock_client.api.get.assert_called_once_with(
            "/search", params={"project": 21, "text": "hello"}
        )

    def test_search_project_no_session_raises(self):
        """Test search_project raises ValueError when no session available."""
        src.server.active_sessions.clear()
        with pytest.raises(ValueError, match="No session_id provided"):
            src.server.search_project(21, "query")


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

    def test_list_resources_sends_disable_pagination_header(self):
        """Test list_resources sends x-disable-pagination header."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        wrapper.api = MagicMock()
        wrapper.api.auth_token = "test-token"
        wrapper.api.get.return_value = [{"id": 1}]
        wrapper.list_resources("projects")
        wrapper.api.get.assert_called_once_with(
            "/projects", params={}, headers={"x-disable-pagination": "True"}
        )

    def test_list_resources_endpoint_mapping(self):
        """Test list_resources maps resource types to correct endpoints."""
        from src.taiga_client import _RESOURCE_ENDPOINTS

        wrapper = TaigaClientWrapper(host="http://test:9000")
        wrapper.api = MagicMock()
        wrapper.api.auth_token = "test-token"
        wrapper.api.get.return_value = []
        for resource_type, endpoint in _RESOURCE_ENDPOINTS.items():
            wrapper.api.get.reset_mock()
            wrapper.list_resources(resource_type)
            call_args = wrapper.api.get.call_args
            assert call_args[0][0] == endpoint, f"{resource_type} -> {endpoint}"

    def test_list_resources_with_filters(self):
        """Test list_resources passes filters as params."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        wrapper.api = MagicMock()
        wrapper.api.auth_token = "test-token"
        wrapper.api.get.return_value = [{"id": 1}]
        result = wrapper.list_resources("issues", project_id=123, status=2)
        wrapper.api.get.assert_called_once_with(
            "/issues",
            params={"project": 123, "status": 2},
            headers={"x-disable-pagination": "True"},
        )
        assert result == [{"id": 1}]

    def test_list_resources_no_project_id(self):
        """Test list_resources omits project key when project_id is None."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        wrapper.api = MagicMock()
        wrapper.api.auth_token = "test-token"
        wrapper.api.get.return_value = [{"id": 1}]
        wrapper.list_resources("projects")
        call_params = wrapper.api.get.call_args[1]["params"]
        assert "project" not in call_params

    def test_list_resources_unknown_type(self):
        """Test list_resources raises for unknown resource type."""
        wrapper = TaigaClientWrapper(host="http://test:9000")
        wrapper.api = MagicMock()
        wrapper.api.auth_token = "test-token"
        with pytest.raises(ValueError, match="Unknown resource type"):
            wrapper.list_resources("nonexistent")

    # ─── _parse_mcp_kwargs JSON error handling tests (PR: fix/kwargs-json-parsing) ──

    def test_parse_mcp_kwargs_valid_json(self):
        """Test that valid JSON in kwargs is parsed correctly."""
        result = src.server._parse_mcp_kwargs({"kwargs": '{"key": "value"}'})
        assert result == {"key": "value"}

    def test_parse_mcp_kwargs_invalid_json_raises_valueerror(self):
        """Test that invalid JSON raises ValueError with descriptive message."""
        with pytest.raises(ValueError, match="Invalid JSON in 'kwargs' parameter"):
            src.server._parse_mcp_kwargs({"kwargs": "{1: 3}"})

    def test_parse_mcp_kwargs_filters_invalid_json_raises_valueerror(self):
        """Test that invalid JSON in 'filters' key raises ValueError with correct key name."""
        with pytest.raises(ValueError, match="Invalid JSON in 'filters' parameter"):
            src.server._parse_mcp_kwargs({"filters": "{bad}"})

    def test_parse_mcp_kwargs_empty_string_returns_empty_dict(self):
        """Test that empty string returns empty dict."""
        result = src.server._parse_mcp_kwargs({"kwargs": ""})
        assert result == {}
