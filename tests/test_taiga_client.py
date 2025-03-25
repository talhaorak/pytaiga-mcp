import unittest
import uuid
import time
from src.taiga_client import TaigaClient, active_sessions, Settings, cleanup_expired_sessions
from src.taiga_client import ProjectCreate, UserStoryCreate, TaskCreate, IssueCreate
import src.taiga_client
from unittest.mock import patch, Mock, MagicMock

class TestTaigaClient(unittest.TestCase):
    def setUp(self):
        # Clear any previously set sessions
        active_sessions.clear()
        # Patch uuid.uuid4 to return a fixed UUID for predictable session IDs
        self.fixed_uuid = uuid.UUID("12345678123456781234567812345678")
        self.uuid_patcher = patch('uuid.uuid4', return_value=self.fixed_uuid)
        self.mock_uuid = self.uuid_patcher.start()
        
        # Mock time functions for predictable test results
        self.time_patcher = patch('time.time', return_value=1000.0)
        self.mock_time = self.time_patcher.start()
        
        # Create a test settings instance
        self.settings_patcher = patch('src.taiga_client.Settings')
        self.mock_settings_class = self.settings_patcher.start()
        self.mock_settings = self.mock_settings_class.return_value
        self.mock_settings.TAIGA_API_URL = "http://example.com"
        self.mock_settings.SESSION_EXPIRY = 28800  # 8 hours
        self.mock_settings.REQUEST_TIMEOUT = 30
        self.mock_settings.MAX_CONNECTIONS = 10
        self.mock_settings.MAX_KEEPALIVE_CONNECTIONS = 5
        self.mock_settings.RATE_LIMIT_REQUESTS = 100

    def tearDown(self):
        self.uuid_patcher.stop()
        self.time_patcher.stop()
        self.settings_patcher.stop()
        active_sessions.clear()

    @patch('httpx.Client')
    @patch('taiga.TaigaAPI')
    def test_authenticate_success(self, mock_taiga_api, mock_httpx_client):
        client = TaigaClient()
        
        # Mock the API authentication
        mock_api = mock_taiga_api.return_value
        mock_api.auth.return_value = None  # No exception means success
        
        result = client.authenticate("valid", "valid", host="http://override.com")
        
        self.assertEqual(result["status"], "authenticated")
        self.assertEqual(result["message"], "Successfully authenticated with Taiga API")
        self.assertIn("session_id", result)
        self.assertEqual(result["expires_in_seconds"], client.settings.SESSION_EXPIRY)
        session_id = result["session_id"]
        self.assertIn(session_id, active_sessions)
        self.assertEqual(active_sessions[session_id]["client"], client)
        
        # Verify API was called correctly
        mock_taiga_api.assert_called_once_with(host="http://override.com")
        mock_api.auth.assert_called_once_with(username="valid", password="valid")

    @patch('httpx.Client')
    @patch('taiga.TaigaAPI')
    def test_authenticate_failure(self, mock_taiga_api, mock_httpx_client):
        client = TaigaClient()
        
        # Mock the API authentication to raise an exception
        mock_api = mock_taiga_api.return_value
        mock_api.auth.side_effect = Exception("Authentication failed")
        
        result = client.authenticate("fail", "fail")
        
        self.assertEqual(result["status"], "error")
        self.assertIn("Authentication failed", result["message"])
    
    @patch('httpx.Client')
    def test_cleanup_expired_sessions(self, mock_httpx_client):
        # Create a valid session
        client1 = TaigaClient()
        session_id1 = str(uuid.uuid4())
        active_sessions[session_id1] = {
            "client": client1,
            "created_at": time.time()  # Current time, should be valid
        }
        
        # Create an expired session (created 9 hours ago)
        client2 = TaigaClient()
        session_id2 = "expired_session"
        active_sessions[session_id2] = {
            "client": client2,
            "created_at": time.time() - 9 * 3600  # 9 hours ago, should be expired
        }
        
        # Run cleanup
        with patch('time.time', return_value=time.time()):
            cleanup_expired_sessions()
        
        # Check that only the valid session remains
        self.assertIn(session_id1, active_sessions)
        self.assertNotIn(session_id2, active_sessions)
    
    @patch('httpx.Client')
    @patch('taiga.TaigaAPI')
    def test_rate_limiting(self, mock_taiga_api, mock_httpx_client):
        client = TaigaClient()
        client.api = mock_taiga_api.return_value
        
        # Set up rate limit
        client.request_count = 99  # Just below the limit
        client.request_count_reset_time = time.time() + 30  # Reset in 30 seconds
        
        # Should work (at the limit)
        client.make_api_call(client.api.projects.list)
        
        # Should fail (exceeds the limit)
        with self.assertRaises(Exception):
            client.make_api_call(client.api.projects.list)
        
        # Reset the rate limit by moving time forward
        with patch('time.time', return_value=time.time() + 61):  # 61 seconds later
            client.make_api_call(client.api.projects.list)  # Should work again after reset
    
    @patch('httpx.Client')
    @patch('taiga.TaigaAPI')
    def test_list_projects(self, mock_taiga_api, mock_httpx_client):
        client = TaigaClient()
        client.api = mock_taiga_api.return_value
        
        # Mock project list
        mock_project1 = Mock()
        mock_project1.id = 1
        mock_project1.name = "Project 1"
        mock_project2 = Mock()
        mock_project2.id = 2
        mock_project2.name = "Project 2"
        
        client.api.projects.list.return_value = [mock_project1, mock_project2]
        
        # Test list_projects
        projects = client.list_projects()
        
        self.assertEqual(len(projects), 2)
        self.assertEqual(projects[0]["id"], 1)
        self.assertEqual(projects[0]["name"], "Project 1")
        self.assertEqual(projects[1]["id"], 2)
        self.assertEqual(projects[1]["name"], "Project 2")
        
        client.api.projects.list.assert_called_once()
    
    @patch('httpx.Client')
    @patch('taiga.TaigaAPI')
    def test_create_project_with_model(self, mock_taiga_api, mock_httpx_client):
        client = TaigaClient()
        client.api = mock_taiga_api.return_value
        
        # Mock project creation
        mock_project = Mock()
        mock_project.id = 1
        mock_project.name = "Test Project"
        mock_project.description = "Test Description"
        
        client.api.projects.create.return_value = mock_project
        
        # Create project using Pydantic model
        project_data = ProjectCreate(
            name="Test Project",
            description="Test Description"
        )
        
        project = client.create_project(project_data)
        
        self.assertEqual(project["id"], 1)
        self.assertEqual(project["name"], "Test Project")
        self.assertEqual(project["description"], "Test Description")
        self.assertEqual(project["status"], "created")
        
        client.api.projects.create.assert_called_with(
            name="Test Project",
            description="Test Description"
        )
    
    @patch('httpx.Client')
    @patch('taiga.TaigaAPI')
    def test_create_project_with_dict(self, mock_taiga_api, mock_httpx_client):
        client = TaigaClient()
        client.api = mock_taiga_api.return_value
        
        # Mock project creation
        mock_project = Mock()
        mock_project.id = 1
        mock_project.name = "Test Project"
        mock_project.description = "Test Description"
        
        client.api.projects.create.return_value = mock_project
        
        # Create project using dictionary
        project_data = {
            "name": "Test Project",
            "description": "Test Description"
        }
        
        project = client.create_project(project_data)
        
        self.assertEqual(project["id"], 1)
        self.assertEqual(project["name"], "Test Project")
        self.assertEqual(project["description"], "Test Description")
        self.assertEqual(project["status"], "created")
        
        client.api.projects.create.assert_called_with(
            name="Test Project",
            description="Test Description"
        )
    
    @patch('httpx.Client')
    @patch('taiga.TaigaAPI')
    def test_get_client_by_session(self, mock_taiga_api, mock_httpx_client):
        # Create a client and add to active sessions
        client = TaigaClient()
        session_id = "test_session"
        active_sessions[session_id] = {
            "client": client,
            "created_at": time.time()
        }
        
        # Get client by session
        retrieved_client = TaigaClient.get_client_by_session(session_id)
        
        self.assertEqual(retrieved_client, client)
        
        # Test with invalid session
        with self.assertRaises(ValueError):
            TaigaClient.get_client_by_session("invalid_session")
        
        # Test with expired session
        expired_session = "expired_session"
        expired_client = TaigaClient()
        active_sessions[expired_session] = {
            "client": expired_client,
            "created_at": time.time() - 9 * 3600  # 9 hours ago, should be expired
        }
        
        with self.assertRaises(ValueError):
            TaigaClient.get_client_by_session(expired_session)
        
        # Expired session should be removed
        self.assertNotIn(expired_session, active_sessions)
    
    @patch('httpx.Client')
    @patch('taiga.TaigaAPI')
    def test_error_handling_decorator(self, mock_taiga_api, mock_httpx_client):
        client = TaigaClient()
        client.api = mock_taiga_api.return_value
        
        # Mock an API call that raises an exception
        client.api.projects.list.side_effect = Exception("Test error")
        
        # Should catch the exception and return an error response
        result = client.list_projects()
        
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_type"], "Exception")
        self.assertEqual(result["message"], "Test error")

if __name__ == "__main__":
    unittest.main()
