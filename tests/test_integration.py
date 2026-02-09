import os
import time
import uuid

import pytest

import src.server
from src.server import (
    create_user_story,
    get_project,
    list_projects,
    list_user_stories,
    login,
    update_project,
)

# Test constants - use environment variables or defaults for testing
TEST_HOST = os.environ.get("TAIGA_TEST_HOST", os.environ.get("TAIGA_API_URL", "http://localhost:9000"))
TEST_USERNAME = os.environ.get("TAIGA_TEST_USERNAME", os.environ.get("TAIGA_USERNAME", "test"))
TEST_PASSWORD = os.environ.get("TAIGA_TEST_PASSWORD", os.environ.get("TAIGA_PASSWORD", "test"))


@pytest.mark.integration  # Mark these to run separately
class TestTaigaIntegration:
    @pytest.fixture
    def session_id(self):
        """Create a real session"""
        result = login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)
        return result["session_id"]

    def test_project_access(self, session_id):
        """Test access to projects using real API calls"""
        # 1. List projects
        projects = list_projects(session_id)

        # Verify we got at least one project
        assert len(projects) > 0, "No projects found in your Taiga account"

        # Prefer Project ID 10 (known working), otherwise avoid corrupted ID 9
        project_id = next((p["id"] for p in projects if p["id"] == 10), None)
        if not project_id:
            project_id = next((p["id"] for p in projects if p["id"] != 9), projects[0]["id"])

        # 2. Get details of a specific project - note: project_id first, then session_id
        project = get_project(project_id, session_id)
        assert project["id"] == project_id

        # Store the original name
        original_name = project["name"]

        try:
            # 3. Update the project with a timestamp - note: project_id first, then kwargs dict, then session_id
            new_name = f"{original_name} (Test {time.time()})"
            updated = update_project(project_id, {"name": new_name}, session_id)
            assert updated["name"] == new_name

        finally:
            # 4. Restore the original name
            update_project(project_id, {"name": original_name}, session_id)

    def test_user_story_workflow(self, session_id):
        """Test user story creation and listing with real API calls"""
        # Get the first project for testing
        projects = list_projects(session_id)
        print(f"DEBUG: Found {len(projects)} projects")  # DEBUG
        assert len(projects) > 0, "No projects found in your Taiga account"
        
        # Prefer Project ID 10 (known working), otherwise avoid corrupted ID 9
        project_id = next((p["id"] for p in projects if p["id"] == 10), None)
        if not project_id:
            project_id = next((p["id"] for p in projects if p["id"] != 9), projects[0]["id"])
        print(f"DEBUG: Using project ID {project_id}")  # DEBUG

        # Create a user story with unique subject
        subject = f"Test Story {uuid.uuid4()}"
        description = "Integration test user story"

        # Create the user story - note: project_id, subject, kwargs dict, session_id
        story = create_user_story(project_id, subject, {"description": description}, session_id)
        print(f"DEBUG: Created story: {story['id']} - {story['subject']}")  # DEBUG
        story_id = story["id"]

        try:
            # Get the list of user stories and verify our story is there - note: project_id first
            time.sleep(1)  # Small delay to ensure creation is complete
            stories = list_user_stories(project_id, None, session_id)

            found = False
            for s in stories:
                if s["id"] == story_id:
                    found = True
                    assert s["subject"] == subject
                    break

            assert found, "Created user story not found in stories list"

        finally:
            # Clean up - mark it as a test that can be ignored/deleted manually
            # Note: story_id, kwargs dict, session_id
            update_user_story = getattr(src.server, "update_user_story", None)
            if update_user_story:
                update_user_story(story_id, {"subject": f"[TEST - CAN DELETE] {subject}"}, session_id)
