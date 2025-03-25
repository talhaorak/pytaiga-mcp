import pytest
from src.taiga_client import TaigaClientError


class TestClientCore:
    """Tests for TaigaClient's core functionality."""
    
    def test_rate_limiting(self, taiga_client, mock_taiga_api, mock_time):
        """Test rate limiting mechanism."""
        # Arrange
        taiga_client.api = mock_taiga_api
        taiga_client.request_count = taiga_client.settings.RATE_LIMIT_REQUESTS - 1  # Just below limit
        taiga_client.request_count_reset_time = mock_time.return_value + 30  # Resets in 30 seconds
        
        # Act - First call should work (at the limit)
        taiga_client.make_api_call(taiga_client.api.projects.list)
        
        # Assert
        assert taiga_client.request_count == taiga_client.settings.RATE_LIMIT_REQUESTS
        
        # Act & Assert - Next call should fail (exceeds the limit)
        with pytest.raises(TaigaClientError) as excinfo:
            taiga_client.make_api_call(taiga_client.api.projects.list)
        
        assert "Rate limit exceeded" in str(excinfo.value)
        
        # Arrange - Reset time counter
        with pytest.patch('time.time', return_value=mock_time.return_value + 61):  # 61 seconds later
            # Act - Should reset and work again
            taiga_client.make_api_call(taiga_client.api.projects.list)
            
            # Assert
            assert taiga_client.request_count == 1  # Counter should be reset

    def test_handle_api_error_decorator(self, taiga_client, mock_taiga_api):
        """Test the error handling decorator."""
        # Arrange
        taiga_client.api = mock_taiga_api
        mock_taiga_api.projects.list.side_effect = Exception("Test error")
        
        # Act
        result = taiga_client.list_projects()
        
        # Assert
        assert result["status"] == "error"
        assert result["error_type"] == "Exception"
        assert result["message"] == "Test error"

    def test_retry_mechanism(self, taiga_client, mock_taiga_api):
        """Test the automatic retry mechanism."""
        # Arrange
        taiga_client.api = mock_taiga_api
        
        # Make the first two calls fail but the third succeed
        side_effects = [
            Exception("First failure"),
            Exception("Second failure"),
            ["project1", "project2"]  # Success on third attempt
        ]
        mock_taiga_api.projects.list.side_effect = side_effects
        
        # Act
        result = taiga_client.make_api_call(mock_taiga_api.projects.list)
        
        # Assert
        assert result == ["project1", "project2"]
        assert mock_taiga_api.projects.list.call_count == 3

    def test_http_client_initialization(self, mock_settings, mock_httpx_client):
        """Test HTTP client initialization with proper settings."""
        # Act
        client = TaigaClient()
        
        # Assert
        mock_httpx_client.assert_called_once()
        
        # Verify timeout and limits were set correctly
        call_kwargs = mock_httpx_client.call_args[1]
        assert call_kwargs["timeout"] == mock_settings.REQUEST_TIMEOUT
        
        limits = call_kwargs["limits"]
        assert limits.max_connections == mock_settings.MAX_CONNECTIONS
        assert limits.max_keepalive_connections == mock_settings.MAX_KEEPALIVE_CONNECTIONS

    def test_client_cleanup_on_deletion(self, taiga_client):
        """Test that HTTP client is closed on deletion."""
        # Arrange
        mock_client = taiga_client.http_client
        
        # Act
        taiga_client.__del__()
        
        # Assert
        mock_client.close.assert_called_once() 