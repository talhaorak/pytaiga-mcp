import json
import os
import time
import uuid

import pytest

import src.server
from src.server import (
    create_user_story,
    delete_user_story,
    get_project,
    list_projects,
    list_user_stories,
    login,
    update_project,
    update_user_story,
)

# Test constants - use environment variables or defaults for testing
TEST_HOST = os.environ.get("TAIGA_TEST_HOST", "http://localhost:9000")
TEST_USERNAME = os.environ.get("TAIGA_TEST_USERNAME", "test")
TEST_PASSWORD = os.environ.get("TAIGA_TEST_PASSWORD", "test")


@pytest.mark.integration
class TestTaigaIntegration:
    @pytest.fixture
    def session_id(self):
        """Create a real session"""
        result = login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)
        sid = result["session_id"]
        yield sid
        # Cleanup session
        src.server.active_sessions.pop(sid, None)

    def test_login(self):
        """Test that login returns a valid session_id."""
        result = login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)
        assert "session_id" in result
        assert result["session_id"] in src.server.active_sessions
        # Cleanup
        src.server.active_sessions.pop(result["session_id"], None)

    def test_project_access(self, session_id):
        """Test access to projects using real API calls"""
        # 1. List projects
        projects = list_projects(session_id)

        # Verify we got at least one project
        assert len(projects) > 0, "No projects found in your Taiga account"

        # Get the first project ID for further tests
        project_id = projects[0]["id"]

        # 2. Get details of a specific project
        project = get_project(project_id, session_id)
        assert project["id"] == project_id

        # Store the original name
        original_name = project["name"]

        try:
            # 3. Update the project with a timestamp
            new_name = f"{original_name} (Test {int(time.time())})"
            updated = update_project(project_id, json.dumps({"name": new_name}), session_id)
            assert updated["name"] == new_name
        finally:
            # 4. Restore the original name
            update_project(project_id, json.dumps({"name": original_name}), session_id)

    def test_user_story_workflow(self, session_id):
        """Test user story creation and listing with real API calls"""
        # Get the first project for testing
        projects = list_projects(session_id)
        assert len(projects) > 0, "No projects found in your Taiga account"
        project_id = projects[0]["id"]

        # Create a user story with unique subject
        subject = f"Test Story {uuid.uuid4()}"
        description = "Integration test user story"

        # Create the user story (project_id, subject, kwargs_json, session_id)
        story = create_user_story(
            project_id, subject, json.dumps({"description": description}), session_id
        )
        story_id = story["id"]

        try:
            # Get the list of user stories and verify our story is there
            time.sleep(1)  # Small delay to ensure creation is complete
            stories = list_user_stories(project_id, "{}", session_id)

            found = any(s["id"] == story_id for s in stories)
            assert found, "Created user story not found in stories list"
        finally:
            # Clean up - delete the test user story
            try:
                delete_user_story(story_id, session_id)
            except Exception:
                # If delete fails, try to rename it for manual cleanup
                try:
                    update_user_story(
                        story_id,
                        json.dumps({"subject": f"[TEST - CAN DELETE] {subject}"}),
                        session_id,
                    )
                except Exception:
                    pass
