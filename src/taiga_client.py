# taiga_client.py
from typing import Optional
import logging
from taiga import TaigaAPI
from taiga.exceptions import TaigaException

# Ensure logger is named correctly for hierarchy
logger = logging.getLogger(__name__)  # No change needed if already done


class TaigaClientWrapper:
    """
    A wrapper around the python-taiga library to manage API instance
    and authentication state. (No functional changes needed from previous version)
    """

    def __init__(self, host: str):
        if not host:
            raise ValueError("Taiga host URL cannot be empty.")
        self.host = host
        self.api: Optional[TaigaAPI] = None  # Use Optional typing
        logger.info(f"TaigaClientWrapper initialized for host: {self.host}")

    def login(self, username: str, password: str) -> bool:
        """
        Authenticates with the Taiga instance using username and password.
        (No functional changes needed from previous version)
        """
        try:
            logger.info(
                f"Attempting login for user '{username}' on {self.host}")
            api_instance = TaigaAPI(host=self.host)
            api_instance.auth(username=username, password=password)
            self.api = api_instance
            logger.info(
                f"Login successful for user '{username}'. Auth token acquired.")
            return True
        except TaigaException as e:
            logger.error(
                f"Taiga login failed for user '{username}': {e}", exc_info=False)
            self.api = None
            raise e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during login for user '{username}': {e}", exc_info=True)
            self.api = None
            raise TaigaException(f"Unexpected login error: {e}")

    @property
    def is_authenticated(self) -> bool:
        """Checks if the client is currently authenticated."""
        return self.api is not None and self.api.token is not None

    def _ensure_authenticated(self):
        """Internal helper to check authentication before API calls."""
        if not self.is_authenticated:
            logger.error(
                "Action required authentication, but client is not logged in.")
            # Use a standard exception type that FastMCP might handle better,
            # or a custom one if needed. PermissionError fits well.
            raise PermissionError(
                "Client not authenticated. Please login first.")
