# taiga_client.py
import logging
from typing import Any, Dict, List, Optional

from pytaigaclient import TaigaClient
from pytaigaclient.exceptions import TaigaException

logger = logging.getLogger(__name__)

# Endpoint mapping for all listable resources
_RESOURCE_ENDPOINTS = {
    "projects": "/projects",
    "user_stories": "/userstories",
    "tasks": "/tasks",
    "issues": "/issues",
    "epics": "/epics",
    "milestones": "/milestones",
    "wiki": "/wiki",
    "memberships": "/memberships",
    "userstory_statuses": "/userstory-statuses",
    "task_statuses": "/task-statuses",
    "issue_statuses": "/issue-statuses",
    "issue_types": "/issue-types",
    "priorities": "/priorities",
    "severities": "/severities",
}

_NO_PAGINATION_HEADERS = {"x-disable-pagination": "True"}


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
            # SECURITY: Don't log username to avoid credential exposure
            logger.info(f"Attempting login on {self.host}")
            # Initialize the client here
            api_instance = TaigaClient(host=self.host)
            # Use the auth resource's login method
            api_instance.auth.login(username=username, password=password)
            self.api = api_instance
            logger.info("Login successful. Auth token acquired.")
            return True
        except TaigaException as e:
            # SECURITY: Don't log username in error messages
            logger.error(f"Taiga login failed: {e}", exc_info=False)
            self.api = None
            raise e
        except Exception as e:
            # SECURITY: Don't log username in error messages
            logger.error(f"An unexpected error occurred during login: {e}", exc_info=True)
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
            logger.error("Action required authentication, but client is not logged in.")
            raise PermissionError("Client not authenticated. Please login first.")

    def list_resources(
        self, resource_type: str, project_id: Optional[int] = None, **filters
    ) -> List[Dict[str, Any]]:
        """
        Unified interface for listing resources via raw API with pagination disabled.

        Uses the x-disable-pagination header to bypass Taiga's default PAGE_SIZE=30
        limit, ensuring all results are returned in a single request.

        Args:
            resource_type: The type of resource (e.g., 'user_stories', 'tasks', 'issues')
            project_id: The project ID to filter by (required for most resources)
            **filters: Additional filters to apply

        Returns:
            List of resource dictionaries
        """
        self._ensure_authenticated()
        endpoint = _RESOURCE_ENDPOINTS.get(resource_type)
        if endpoint is None:
            raise ValueError(
                f"Unknown resource type: {resource_type}. Valid: {sorted(_RESOURCE_ENDPOINTS)}"
            )
        params = {}
        if project_id is not None:
            params["project"] = project_id
        params.update(filters)
        result = self.api.get(endpoint, params=params, headers=_NO_PAGINATION_HEADERS)
        return result if isinstance(result, list) else []
