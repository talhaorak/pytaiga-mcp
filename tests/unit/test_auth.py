import pytest
import time
from src.taiga_client import TaigaClient, active_sessions, cleanup_expired_sessions


class TestAuthentication:
    """Tests for authentication and session management."""
    
    def test_authenticate_success(self, taiga_client, mock_taiga_api, mock_uuid):
        """Test successful authentication."""
        # Arrange
        mock_taiga_api.auth.return_value = None  # No exception means success
        taiga_client.api = mock_taiga_api
        
        # Act
        result = taiga_client.authenticate("valid", "valid", host="http://override.com")
        
        # Assert
        assert result["status"] == "authenticated"
        assert result["message"] == "Successfully authenticated with Taiga API"
        assert "session_id" in result
        assert result["expires_in_seconds"] == taiga_client.settings.SESSION_EXPIRY
        
        session_id = result["session_id"]
        assert session_id in active_sessions
        assert active_sessions[session_id]["client"] == taiga_client
        
        # Verify API was called correctly
        mock_taiga_api.auth.assert_called_once_with(username="valid", password="valid")

    def test_authenticate_failure(self, taiga_client, mock_taiga_api):
        """Test failed authentication."""
        # Arrange
        mock_taiga_api.auth.side_effect = Exception("Authentication failed")
        taiga_client.api = mock_taiga_api
        
        # Act
        result = taiga_client.authenticate("fail", "fail")
        
        # Assert
        assert result["status"] == "error"
        assert "Authentication failed" in result["message"]

    def test_get_client_by_session_valid(self, authenticated_client):
        """Test retrieving client by valid session ID."""
        # Arrange
        client, session_id = authenticated_client
        
        # Act
        retrieved_client = TaigaClient.get_client_by_session(session_id)
        
        # Assert
        assert retrieved_client == client

    def test_get_client_by_session_invalid(self):
        """Test retrieving client by invalid session ID."""
        # Act & Assert
        with pytest.raises(ValueError) as excinfo:
            TaigaClient.get_client_by_session("invalid_session")
        
        assert "Invalid or expired session ID" in str(excinfo.value)

    def test_get_client_by_session_expired(self, taiga_client, mock_time):
        """Test retrieving client by expired session ID."""
        # Arrange
        session_id = "expired_session"
        active_sessions[session_id] = {
            "client": taiga_client,
            "created_at": time.time() - 9 * 3600  # 9 hours ago (expired)
        }
        
        # Act & Assert
        with pytest.raises(ValueError) as excinfo:
            TaigaClient.get_client_by_session(session_id)
        
        assert "expired" in str(excinfo.value)
        assert session_id not in active_sessions  # Should remove expired session

    def test_logout_success(self, authenticated_client):
        """Test successful logout."""
        # Arrange
        _, session_id = authenticated_client
        
        # Act
        result = TaigaClient.logout(session_id)
        
        # Assert
        assert result["status"] == "success"
        assert "Logged out successfully" in result["message"]
        assert session_id not in active_sessions

    def test_logout_invalid_session(self):
        """Test logout with invalid session ID."""
        # Act
        result = TaigaClient.logout("invalid_session")
        
        # Assert
        assert result["status"] == "error"
        assert "Invalid session ID" in result["message"]

    def test_cleanup_expired_sessions(self, taiga_client, mock_time):
        """Test cleanup of expired sessions."""
        # Arrange
        valid_session = "valid_session"
        expired_session = "expired_session"
        
        active_sessions[valid_session] = {
            "client": taiga_client,
            "created_at": time.time()  # Current time (valid)
        }
        
        active_sessions[expired_session] = {
            "client": taiga_client,
            "created_at": time.time() - 9 * 3600  # 9 hours ago (expired)
        }
        
        # Act
        cleanup_expired_sessions()
        
        # Assert
        assert valid_session in active_sessions
        assert expired_session not in active_sessions 