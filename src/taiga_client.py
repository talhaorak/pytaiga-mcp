# taiga_client.py
from typing import Optional
import logging
# Replace python-taiga import
# from taiga import TaigaAPI
# from taiga.exceptions import TaigaException
from pytaigaclient import TaigaClient  # Import the new client
# Assuming pytaigaclient also has a base exception
from pytaigaclient.exceptions import TaigaException

# Ensure logger is named correctly for hierarchy
logger = logging.getLogger(__name__)


class TaigaClientWrapper:
    """
    A wrapper around the pytaiga-client library to manage API instance
    and authentication state.
    """

    def __init__(self, host: str):
        if not host:
            raise ValueError("Taiga host URL cannot be empty.")
        # Store host, but initialize client later during login/token auth
        self.host = host
        # Use the new client type
        self.api: Optional[TaigaClient] = None
        logger.info(f"TaigaClientWrapper initialized for host: {self.host}")

    def login(self, username: str, password: str) -> bool:
        """
        Authenticates with the Taiga instance using username and password.
        Uses pytaigaclient.
        """
        try:
            logger.info(
                f"Attempting login for user '{username}' on {self.host}")
            # Initialize the client here
            api_instance = TaigaClient(host=self.host)
            # Use the auth resource's login method
            api_instance.auth.login(username=username, password=password)
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
            # Wrap unexpected errors in TaigaException if needed, or re-raise
            raise TaigaException(f"Unexpected login error: {e}")

    # Add method for token authentication if needed by pytaigaclient
    # def set_token(self, token: str, token_type: str = "Bearer"):
    #     logger.info(f"Initializing TaigaClient with token on {self.host}")
    #     self.api = TaigaClient(host=self.host, auth_token=token, token_type=token_type)
    #     logger.info("TaigaClient initialized with token.")

    @property
    def is_authenticated(self) -> bool:
        """Checks if the client is currently authenticated (has an API instance with a token)."""
        # Check if api exists and has a token
        return self.api is not None and self.api.auth_token is not None

    def _ensure_authenticated(self):
        """Internal helper to check authentication before API calls."""
        if not self.is_authenticated:
            logger.error(
                "Action required authentication, but client is not logged in.")
            # Use a standard exception type that FastMCP might handle better,
            # or a custom one if needed. PermissionError fits well.
            raise PermissionError(
                "Client not authenticated. Please login first.")

# No changes needed to _ensure_authenticated or is_authenticated property logic,
# just the types and method calls within login.
