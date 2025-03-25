import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.server import periodic_session_cleanup
from fastapi import FastAPI
from contextlib import asynccontextmanager


@pytest.mark.asyncio
async def test_periodic_session_cleanup():
    """Test the periodic session cleanup function."""
    # Mock cleanup function
    with patch('src.server.cleanup_expired_sessions') as mock_cleanup:
        # Mock sleep to avoid actually sleeping
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Set sleep to raise CancelledError after first call
            mock_sleep.side_effect = [None, asyncio.CancelledError()]
            
            # Run the function and expect CancelledError
            with pytest.raises(asyncio.CancelledError):
                await periodic_session_cleanup()
            
            # Verify cleanup was called once
            mock_cleanup.assert_called_once()
            # Verify sleep was called once with 300 seconds (5 minutes)
            mock_sleep.assert_called_with(300)


@pytest.mark.asyncio
async def test_app_lifespan():
    """Test the FastAPI app lifespan setup."""
    # Create mock FastAPI app
    app = MagicMock()
    
    # Mock the asynccontextmanager to capture the lifespan generator
    with patch('src.server.asynccontextmanager', side_effect=asynccontextmanager) as mock_ctx:
        # Import lifespan to trigger the mock
        from src.server import lifespan
        
        # Mock cleanup task
        cleanup_task = MagicMock()
        
        # Mock create_task to return our mock task
        with patch('asyncio.create_task', return_value=cleanup_task) as mock_create_task:
            # Execute the lifespan generator
            async with lifespan(app):
                # Verify task was created
                mock_create_task.assert_called_once()
                assert cleanup_task.cancel.call_count == 0
            
            # After context exit, verify task was cancelled
            cleanup_task.cancel.assert_called_once()


def test_command_line_args():
    """Test command line argument parsing."""
    # Mock argparse
    mock_parser = MagicMock()
    mock_parser.parse_args.return_value = MagicMock(
        sse=True,
        host="127.0.0.1",
        port=8000
    )
    
    with patch('src.server.argparse.ArgumentParser', return_value=mock_parser):
        # Import to trigger the mock
        import importlib
        import src.server
        importlib.reload(src.server)
        
        # Verify parser was created with expected arguments
        mock_parser.add_argument.assert_any_call("--sse", action="store_true", 
            help="Use SSE transport mode (default is stdio)")
        mock_parser.add_argument.assert_any_call("--host", type=str, default="127.0.0.1", 
            help="Host to bind to for HTTP server")
        mock_parser.add_argument.assert_any_call("--port", type=int, default=8000, 
            help="Port to bind to for HTTP server") 