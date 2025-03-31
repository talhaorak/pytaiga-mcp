import pytest
import uuid
import time
import src.server
from src.server import login, list_projects, update_project, get_project, list_user_stories, create_user_story

# Test constants - use a real Taiga test instance!
TEST_HOST = "http://localhost:9000"
TEST_USERNAME = "test"  
TEST_PASSWORD = "test"

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
        
        # Get the first project ID for further tests
        project_id = projects[0]["id"]
        
        # 2. Get details of a specific project
        project = get_project(session_id, project_id)
        assert project["id"] == project_id
        
        # Store the original name
        original_name = project["name"]
        
        try:
            # 3. Update the project with a timestamp
            new_name = f"{original_name} (Test {time.time()})"
            updated = update_project(session_id, project_id, name=new_name)
            assert updated["name"] == new_name
            
        finally:
            # 4. Restore the original name
            update_project(session_id, project_id, name=original_name)
    
    def test_user_story_workflow(self, session_id):
        """Test user story creation and listing with real API calls"""
        # Get the first project for testing
        projects = list_projects(session_id)
        print(f"DEBUG: Found {len(projects)} projects") # DEBUG
        assert len(projects) > 0, "No projects found in your Taiga account"
        project_id = projects[0]["id"]
        print(f"DEBUG: Using project ID {project_id}") # DEBUG
        
        # Create a user story with unique subject
        subject = f"Test Story {uuid.uuid4()}"
        description = "Integration test user story"
        
        # Create the user story
        # BREAKPOINT: Set a breakpoint on the next line to debug story creation
        story = create_user_story(session_id, project_id, subject, description=description)
        print(f"DEBUG: Created story: {story['id']} - {story['subject']}") # DEBUG
        story_id = story["id"]
        
        try:
            # Get the list of user stories and verify our story is there
            time.sleep(1)  # Small delay to ensure creation is complete
            stories = list_user_stories(session_id, project_id)
            
            found = False
            for s in stories:
                if s["id"] == story_id:
                    found = True
                    assert s["subject"] == subject
                    break
            
            assert found, "Created user story not found in stories list"
            
        finally:
            # Clean up - normally we would delete the story, but there's no delete_user_story
            # So we'll update it to mark it as a test that can be ignored/deleted manually
            update_user_story = getattr(src.server, "update_user_story", None)
            if update_user_story:
                update_user_story(session_id, story_id, subject=f"[TEST - CAN DELETE] {subject}")
