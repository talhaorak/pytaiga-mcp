import pytest
import responses
import json
import re
from unittest.mock import patch
from src.taiga_client import TaigaClient


@pytest.fixture
def taiga_base_url():
    return "http://taiga.test"


@pytest.fixture
def taiga_client_with_real_http(taiga_base_url):
    """Create a TaigaClient with real HTTP but mocked responses."""
    with patch('src.taiga_client.Settings') as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.TAIGA_API_URL = taiga_base_url
        mock_settings.SESSION_EXPIRY = 28800
        mock_settings.REQUEST_TIMEOUT = 30
        mock_settings.MAX_CONNECTIONS = 10
        mock_settings.MAX_KEEPALIVE_CONNECTIONS = 5
        mock_settings.RATE_LIMIT_REQUESTS = 100
        
        client = TaigaClient(host=taiga_base_url)
        yield client


@pytest.mark.integration
class TestTaigaClientIntegration:
    """Integration tests for TaigaClient."""
    
    @responses.activate
    def test_authentication_flow(self, taiga_client_with_real_http, taiga_base_url):
        """Test the complete authentication flow with mocked HTTP responses."""
        # Mock the auth endpoint
        responses.add(
            responses.POST,
            f"{taiga_base_url}/api/v1/auth",
            json={
                "auth_token": "dummy-token",
                "refresh": "dummy-refresh",
                "id": 123,
                "username": "testuser"
            },
            status=200
        )
        
        # Mock the user details endpoint
        responses.add(
            responses.GET,
            re.compile(f"{taiga_base_url}/api/v1/users/me"),
            json={
                "id": 123,
                "username": "testuser",
                "email": "test@example.com",
                "full_name": "Test User"
            },
            status=200
        )
        
        # Authenticate
        result = taiga_client_with_real_http.authenticate("testuser", "password")
        
        # Check response
        assert result["status"] == "authenticated"
        assert "session_id" in result
        
        # Get the session ID for further tests
        session_id = result["session_id"]
        
        # Test logout
        logout_result = TaigaClient.logout(session_id)
        assert logout_result["status"] == "success"
    
    @responses.activate
    def test_project_workflow(self, taiga_client_with_real_http, taiga_base_url):
        """Test a complete project workflow with mocked HTTP responses."""
        # Mock auth (needed to initialize)
        responses.add(
            responses.POST,
            f"{taiga_base_url}/api/v1/auth",
            json={"auth_token": "dummy-token", "id": 123},
            status=200
        )
        
        # Mock user details
        responses.add(
            responses.GET,
            re.compile(f"{taiga_base_url}/api/v1/users/me"),
            json={"id": 123, "username": "testuser"},
            status=200
        )
        
        # Mock project creation
        responses.add(
            responses.POST,
            f"{taiga_base_url}/api/v1/projects",
            json={
                "id": 1,
                "name": "Test Project",
                "description": "Test Description",
                "owner": {"id": 123}
            },
            status=201
        )
        
        # Mock project list
        responses.add(
            responses.GET,
            f"{taiga_base_url}/api/v1/projects",
            json=[
                {
                    "id": 1,
                    "name": "Test Project",
                    "description": "Test Description"
                }
            ],
            status=200
        )
        
        # Mock get specific project
        responses.add(
            responses.GET,
            f"{taiga_base_url}/api/v1/projects/1",
            json={
                "id": 1,
                "name": "Test Project",
                "description": "Test Description"
            },
            status=200
        )
        
        # Mock project update
        responses.add(
            responses.PATCH,
            f"{taiga_base_url}/api/v1/projects/1",
            json={
                "id": 1,
                "name": "Updated Project",
                "description": "Updated Description"
            },
            status=200
        )
        
        # Mock project delete
        responses.add(
            responses.DELETE,
            f"{taiga_base_url}/api/v1/projects/1",
            status=204
        )
        
        # Authenticate
        client = taiga_client_with_real_http
        client.authenticate("testuser", "password")
        
        # Create a project
        create_result = client.create_project({
            "name": "Test Project",
            "description": "Test Description"
        })
        assert create_result["name"] == "Test Project"
        assert create_result["id"] == 1
        
        # List projects
        list_result = client.list_projects()
        assert len(list_result) == 1
        assert list_result[0]["name"] == "Test Project"
        
        # Get specific project
        get_result = client.get_project(1)
        assert get_result["name"] == "Test Project"
        assert get_result["id"] == 1
        
        # Update project
        update_result = client.update_project(1, name="Updated Project", description="Updated Description")
        assert update_result["name"] == "Updated Project"
        assert update_result["description"] == "Updated Description"
        
        # Delete project
        delete_result = client.delete_project(1)
        assert delete_result["status"] == "deleted" 