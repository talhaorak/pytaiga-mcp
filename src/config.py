"""Configuration management with secure credential handling."""

from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

# Get the project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"

# Load .env file from project root
load_dotenv(dotenv_path=ENV_FILE_PATH)


class TaigaSettings(BaseSettings):
    """Taiga MCP server settings with secure credential handling."""

    # Connection settings
    host: str = Field(
        default="http://localhost:9000",
        alias="TAIGA_API_URL",
        description="Taiga API base URL",
    )

    # Credentials (using SecretStr for security)
    username: Optional[SecretStr] = Field(
        default=None,
        alias="TAIGA_USERNAME",
        description="Taiga username for auto-authentication",
    )
    password: Optional[SecretStr] = Field(
        default=None,
        alias="TAIGA_PASSWORD",
        description="Taiga password for auto-authentication",
    )

    class Config:
        env_file = str(ENV_FILE_PATH)
        env_file_encoding = "utf-8"
        extra = "ignore"
        populate_by_name = True

    @property
    def has_credentials(self) -> bool:
        """Check if credentials are available for auto-auth."""
        return bool(self.username and self.password)

    def get_username_value(self) -> Optional[str]:
        """Safely get username value."""
        return self.username.get_secret_value() if self.username else None

    def get_password_value(self) -> Optional[str]:
        """Safely get password value."""
        return self.password.get_secret_value() if self.password else None


def mask_credential(value: str, visible_chars: int = 2) -> str:
    """Mask a credential for safe logging.

    Args:
        value: The credential to mask
        visible_chars: Number of characters to show at start/end

    Returns:
        Masked string like "us****rd"
    """
    if not value:
        return "<empty>"
    if len(value) <= visible_chars * 2:
        return "*" * len(value)
    return f"{value[:visible_chars]}{'*' * (len(value) - visible_chars * 2)}{value[-visible_chars:]}"


# Global settings instance
settings = TaigaSettings()
