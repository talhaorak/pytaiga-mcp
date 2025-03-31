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
        
        # Setup mock project
        mock_project = MagicMock()
        mock_project.id = 123
        mock_project.name = "Test Project"
        mock_project.to_dict.return_value = {"id": 123, "name": "Test Project"}
        
        # Setup list projects return
        mock_client.api.projects.list.return_value = [mock_project]
        
        # List projects and verify
        projects = src.server.list_projects(session_id)
        assert len(projects) == 1
        assert projects[0]["name"] == "Test Project"
        assert projects[0]["id"] == 123
    
    def test_update_project(self, session_setup):
        """Test update_project functionality"""
        session_id, mock_client = session_setup
        
        # Setup mock project
        mock_project = MagicMock()
        mock_project.id = 123
        mock_project.name = "Old Name"
        
        # Setup allowed parameters for the project model
        mock_client.api.projects.instance = MagicMock()
        mock_client.api.projects.instance.allowed_params = ['name', 'description']
        
        # Setup get project return
        mock_client.api.projects.get.return_value = mock_project
        
        # Update the project name
        result = src.server.update_project(session_id, 123, name="New Name")
        
        # Verify the update was called
        mock_project.update.assert_called_once()
        assert mock_project.name == "New Name"
    
    def test_list_user_stories(self, session_setup):
        """Test list_user_stories functionality"""
        session_id, mock_client = session_setup
        
        # Setup mock user story
        mock_story = MagicMock()
        mock_story.id = 456
        mock_story.subject = "Test User Story"
        mock_story.to_dict.return_value = {"id": 456, "subject": "Test User Story"}
        
        # Setup list user stories return
        mock_client.api.user_stories.list.return_value = [mock_story]
        
        # List user stories and verify
        stories = src.server.list_user_stories(session_id, 123)
        assert len(stories) == 1
        assert stories[0]["subject"] == "Test User Story"
        assert stories[0]["id"] == 456
        
        # Verify the correct project filter was used
        mock_client.api.user_stories.list.assert_called_once_with(project=123)
    
    def test_create_user_story(self, session_setup):
        """Test create_user_story functionality"""
        session_id, mock_client = session_setup
        
        # Setup mock user story
        mock_story = MagicMock()
        mock_story.id = 456
        mock_story.subject = "New Story"
        mock_story.to_dict.return_value = {"id": 456, "subject": "New Story"}
        
        # Setup create user story return
        mock_client.api.user_stories.create.return_value = mock_story
        
        # Create user story and verify
        story = src.server.create_user_story(session_id, 123, "New Story", description="Test description")
        assert story["subject"] == "New Story"
        assert story["id"] == 456
        
        # Verify the create was called with correct parameters
        mock_client.api.user_stories.create.assert_called_once_with(123, "New Story", description="Test description")
    
    def test_list_tasks(self, session_setup):
        """Test list_tasks functionality"""
        session_id, mock_client = session_setup
        
        # Setup mock task
        mock_task = MagicMock()
        mock_task.id = 789
        mock_task.subject = "Test Task"
        mock_task.to_dict.return_value = {"id": 789, "subject": "Test Task"}
        
        # Setup list tasks return
        mock_client.api.tasks.list.return_value = [mock_task]
        
        # List tasks and verify
        tasks = src.server.list_tasks(session_id, 123)
        assert len(tasks) == 1
        assert tasks[0]["subject"] == "Test Task"
        assert tasks[0]["id"] == 789
        
        # Verify the correct project filter was used
        mock_client.api.tasks.list.assert_called_once_with(project=123)
