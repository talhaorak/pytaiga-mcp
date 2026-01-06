import pytest
import uuid
from unittest.mock import patch, MagicMock

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
            
            # Get the session ID for cleanup
            session_id = result["session_id"]
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

        # Update the project name - note: project_id first, then session_id
        result = src.server.update_project(123, session_id, name="New Name")

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

        # List user stories and verify - note: project_id first, then session_id
        stories = src.server.list_user_stories(123, session_id)
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

        # Create user story and verify - note: project_id first, subject second, then session_id
        story = src.server.create_user_story(123, "New Story", session_id, description="Test description")
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

        # List tasks and verify - note: project_id first, then session_id
        tasks = src.server.list_tasks(123, session_id)
        assert len(tasks) == 1
        assert tasks[0]["subject"] == "Test Task"
        assert tasks[0]["id"] == 789

        # Verify the correct API call was made (uses get instead of tasks.list due to bug workaround)
        mock_client.api.get.assert_called_once_with("/tasks", params={"project": 123})
