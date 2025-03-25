from mcp.server.fastmcp import FastMCP
from taiga_client import TaigaClient, active_sessions, cleanup_expired_sessions
import os
import time
import sys
import argparse
import logging
import json
import asyncio
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from config import Settings
from tools import mcp


# Configure logging based on settings
settings = Settings()
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.LOG_FILE)
    ]
)
logger = logging.getLogger('taiga_mcp')


# Create FastAPI app for potential HTTP endpoints
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize resources
    logger.info("Starting Taiga MCP Bridge Server")
    
    # Set up session cleanup background task
    session_cleanup_task = asyncio.create_task(periodic_session_cleanup())
    
    # Yield control back to FastAPI
    yield
    
    # Shutdown: cleanup resources
    logger.info("Shutting down Taiga MCP Bridge Server")
    session_cleanup_task.cancel()
    try:
        await session_cleanup_task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Can be updated to be more restrictive in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Background task for session cleanup
async def periodic_session_cleanup():
    """Periodically clean up expired sessions."""
    while True:
        try:
            logger.debug("Running session cleanup")
            cleanup_expired_sessions()
            await asyncio.sleep(300)  # Run every 5 minutes
        except asyncio.CancelledError:
            logger.info("Session cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in session cleanup: {e}")
            await asyncio.sleep(60)  # Retry after a minute on error


# Parse command line arguments
parser = argparse.ArgumentParser(description="Taiga MCP Bridge Server")
parser.add_argument("--sse", action="store_true", help="Use SSE transport mode (default is stdio)")
parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind to for HTTP server")
parser.add_argument("--port", type=int, default=8000, help="Port to bind to for HTTP server")
args = parser.parse_args()


# Determine transport mode from CLI args or environment
if args.sse:
    transport_mode = "sse"
else:
    # Check environment variable if CLI flag not set
    transport_mode = settings.TRANSPORT_MODE

# Validate transport mode
if transport_mode not in ["stdio", "sse"]:
    logger.warning(f"Invalid transport mode: {transport_mode}. Using default 'stdio'")
    transport_mode = "stdio"


# Start the server
if __name__ == "__main__":
    try:
        logger.info(f"Starting MCP server with transport mode: {transport_mode}")
        mcp.run(transport=transport_mode)
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)
