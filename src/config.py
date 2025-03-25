import os
from dotenv import load_dotenv
from pydantic import BaseSettings, Field, validator
from typing import Optional, Dict, Any

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Configuration settings for the Taiga MCP Bridge with validation"""
    
    # Taiga API connection settings
    TAIGA_API_URL: str = Field(
        default=os.getenv("TAIGA_API_URL", "http://localhost:9000"),
        description="Base URL for the Taiga API"
    )
    
    # Session management
    SESSION_EXPIRY: int = Field(
        default=int(os.getenv("SESSION_EXPIRY", "28800")),
        description="Session expiration time in seconds (default: 8 hours)",
        ge=60  # Must be at least 60 seconds
    )
    
    # Transport configuration
    TRANSPORT_MODE: str = Field(
        default=os.getenv("TAIGA_TRANSPORT", "stdio").lower(),
        description="Transport mode for MCP communication (stdio or sse)"
    )
    
    # API request settings
    REQUEST_TIMEOUT: int = Field(
        default=int(os.getenv("REQUEST_TIMEOUT", "30")),
        description="Timeout for API requests in seconds",
        ge=1
    )
    
    # Connection pooling settings
    MAX_CONNECTIONS: int = Field(
        default=int(os.getenv("MAX_CONNECTIONS", "10")),
        description="Maximum number of concurrent connections",
        ge=1
    )
    
    MAX_KEEPALIVE_CONNECTIONS: int = Field(
        default=int(os.getenv("MAX_KEEPALIVE_CONNECTIONS", "5")),
        description="Maximum number of connections to keep alive",
        ge=1
    )
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = Field(
        default=int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
        description="Maximum number of requests per minute",
        ge=1
    )
    
    # Logging configuration
    LOG_LEVEL: str = Field(
        default=os.getenv("LOG_LEVEL", "INFO").upper(),
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    LOG_FILE: str = Field(
        default=os.getenv("LOG_FILE", "taiga_mcp.log"),
        description="Path to log file"
    )
    
    @validator('TRANSPORT_MODE')
    def validate_transport_mode(cls, v):
        if v not in ["stdio", "sse"]:
            raise ValueError(f"Invalid transport mode: {v}. Must be 'stdio' or 'sse'")
        return v
    
    @validator('LOG_LEVEL')
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
