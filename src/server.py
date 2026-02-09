# server.py
import json
import logging
import logging.config
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from pytaigaclient.exceptions import TaigaException

from src.config import settings
from src.taiga_client import TaigaClientWrapper

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()  # Log to stderr by default
    ],
)
logger = logging.getLogger(__name__)
# Quiet down pytaigaclient library logging if needed
logging.getLogger("pytaigaclient").setLevel(logging.WARNING)

# --- Helper Functions ---


def _parse_mcp_kwargs(kwargs: dict) -> dict:
    """Parse MCP kwargs which may be passed as a JSON string.

    When FastMCP receives **kwargs in a tool function, it may pass
    additional parameters as a JSON string under the 'kwargs' or 'filters' key.
    This function handles that case and returns a proper dict.
    """
    if not kwargs:
        return {}
    # If kwargs contains a single key with a string value, parse it as JSON
    if len(kwargs) == 1:
        key = next(iter(kwargs))
        if key in ("kwargs", "filters"):
            val = kwargs[key]
            if isinstance(val, str):
                return json.loads(val) if val else {}
            return val if isinstance(val, dict) else {}
    return kwargs


# --- Kwargs Validation ---
# Allowed kwargs per resource type for security and validation
# Based on Taiga API fields: https://docs.taiga.io/api.html
ALLOWED_KWARGS: Dict[str, set] = {
    "project": {
        "name",
        "is_private",
        "is_featured",
        "description",
        "tags",
        "total_story_points",
        "total_milestones",
        "is_looking_for_people",
        "looking_for_people_note",
        "is_epics_activated",
        "is_backlog_activated",
        "is_kanban_activated",
        "is_wiki_activated",
        "is_issues_activated",
        "videoconferences",
        "videoconferences_extra_data",
        "creation_template",
        "is_contact_activated",
    },
    "user_story": {
        "subject",
        "description",
        "status",
        "is_closed",
        "points",
        "milestone",
        "tags",
        "assigned_to",
        "assigned_users",
        "watchers",
        "client_requirement",
        "team_requirement",
        "is_blocked",
        "blocked_note",
        "backlog_order",
        "sprint_order",
        "kanban_order",
        "due_date",
        "due_date_reason",
        "epics",
    },
    "task": {
        "subject",
        "description",
        "status",
        "milestone",
        "user_story",
        "assigned_to",
        "watchers",
        "is_iocaine",
        "tags",
        "is_blocked",
        "blocked_note",
        "due_date",
        "due_date_reason",
        "taskboard_order",
    },
    "issue": {
        "subject",
        "description",
        "status",
        "priority",
        "severity",
        "type",
        "milestone",
        "assigned_to",
        "watchers",
        "tags",
        "is_blocked",
        "blocked_note",
        "due_date",
        "due_date_reason",
    },
    "epic": {
        "subject",
        "description",
        "status",
        "assigned_to",
        "watchers",
        "tags",
        "color",
        "client_requirement",
        "team_requirement",
        "epics_order",
    },
    "milestone": {
        "name",
        "estimated_start",
        "estimated_finish",
        "disponibility",
        "slug",
        "order",
        "watchers",
    },
    "wiki_page": {
        "slug",
        "content",
    },
}

# --- Response Field Filtering ---
# Define which fields to include at each verbosity level per resource type
# - 'minimal': Core identification fields only
# - 'standard': Useful fields for typical AI operations (includes 'version' for updates)
# - 'full': None = return all fields (no filtering)
RESPONSE_FIELDS: Dict[str, Dict[str, Optional[List[str]]]] = {
    "project": {
        "minimal": ["id", "name", "slug"],
        "standard": [
            "id",
            "name",
            "slug",
            "description",
            "is_private",
            "tags",
            "created_date",
            "modified_date",
            "version",
        ],
        "full": None,
    },
    "user_story": {
        "minimal": ["id", "ref", "subject", "status", "project"],
        "standard": [
            "id",
            "ref",
            "subject",
            "description",
            "status",
            "status_extra_info",
            "assigned_to",
            "assigned_to_extra_info",
            "milestone",
            "project",
            "tags",
            "is_blocked",
            "is_closed",
            "due_date",
            "version",
        ],
        "full": None,
    },
    "task": {
        "minimal": ["id", "ref", "subject", "status", "project"],
        "standard": [
            "id",
            "ref",
            "subject",
            "description",
            "status",
            "status_extra_info",
            "assigned_to",
            "assigned_to_extra_info",
            "user_story",
            "milestone",
            "project",
            "tags",
            "is_blocked",
            "due_date",
            "version",
        ],
        "full": None,
    },
    "issue": {
        "minimal": ["id", "ref", "subject", "status", "priority", "severity", "project"],
        "standard": [
            "id",
            "ref",
            "subject",
            "description",
            "status",
            "status_extra_info",
            "priority",
            "priority_extra_info",
            "severity",
            "severity_extra_info",
            "type",
            "type_extra_info",
            "assigned_to",
            "assigned_to_extra_info",
            "milestone",
            "project",
            "tags",
            "is_blocked",
            "due_date",
            "version",
        ],
        "full": None,
    },
    "epic": {
        "minimal": ["id", "ref", "subject", "status", "project"],
        "standard": [
            "id",
            "ref",
            "subject",
            "description",
            "status",
            "status_extra_info",
            "assigned_to",
            "assigned_to_extra_info",
            "project",
            "tags",
            "color",
            "version",
        ],
        "full": None,
    },
    "milestone": {
        "minimal": ["id", "name", "slug", "project"],
        "standard": [
            "id",
            "name",
            "slug",
            "estimated_start",
            "estimated_finish",
            "closed",
            "project",
            "version",
        ],
        "full": None,
    },
    "member": {
        "minimal": ["id", "user", "full_name"],
        "standard": [
            "id",
            "user",
            "full_name",
            "email",
            "role",
            "role_name",
            "is_admin",
            "project",
        ],
        "full": None,
    },
    "wiki_page": {
        "minimal": ["id", "slug", "project"],
        "standard": ["id", "slug", "content", "project", "version"],
        "full": None,
    },
}

VALID_VERBOSITY_LEVELS = {"minimal", "standard", "full"}


def _validate_kwargs(resource_type: str, kwargs: dict, strict: bool = False) -> dict:
    """Validate kwargs against allowed fields for a resource type.

    Args:
        resource_type: The type of resource (e.g., 'project', 'user_story')
        kwargs: The kwargs dict to validate
        strict: If True, raise ValueError on unexpected kwargs. If False, log and strip.

    Returns:
        Validated kwargs dict with only allowed fields

    Raises:
        ValueError: If strict=True and unexpected kwargs are found
    """
    if not kwargs:
        return {}

    allowed = ALLOWED_KWARGS.get(resource_type)
    if allowed is None:
        # Unknown resource type - pass through but log warning
        logger.warning(f"No kwargs allowlist defined for resource type '{resource_type}'")
        return kwargs

    unexpected = set(kwargs.keys()) - allowed
    if unexpected:
        if strict:
            raise ValueError(
                f"Unexpected kwargs for {resource_type}: {unexpected}. Allowed: {allowed}"
            )
        else:
            logger.warning(f"Stripping unexpected kwargs for {resource_type}: {unexpected}")
            return {k: v for k, v in kwargs.items() if k in allowed}

    return kwargs


# --- Manual Session Management ---
# Store active sessions: session_id -> TaigaClientWrapper instance
active_sessions: Dict[str, TaigaClientWrapper] = {}

# Reserved session ID for auto-authenticated session from environment variables
DEFAULT_SESSION_ID = "default"


# --- Lifespan for Auto-Authentication ---
@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """
    Manage server startup and shutdown lifecycle.
    Performs auto-authentication if credentials are in environment.
    """
    if settings.has_credentials:
        logger.info("Environment credentials detected. Attempting auto-authentication...")
        try:
            wrapper = TaigaClientWrapper(host=settings.host)
            success = wrapper.login(
                username=settings.get_username_value(), password=settings.get_password_value()
            )
            if success:
                active_sessions[DEFAULT_SESSION_ID] = wrapper
                logger.info(
                    f"Auto-authentication successful. Default session created: '{DEFAULT_SESSION_ID}'"
                )
            else:
                logger.warning("Auto-authentication failed. Manual login required.")
        except Exception as e:
            logger.error(f"Auto-authentication error: {e}")
            logger.warning("Continuing without auto-authentication. Manual login required.")
    else:
        logger.info("No environment credentials found. Manual login required via login() tool.")

    try:
        yield
    finally:
        # Cleanup on shutdown
        logger.info("Server shutting down. Cleaning up sessions...")
        active_sessions.clear()


# --- MCP Server Definition ---
mcp = FastMCP("Taiga Bridge", dependencies=["pytaigaclient"], lifespan=server_lifespan)

# --- Helper Functions for Session Validation ---


def _get_session_id(session_id: Optional[str] = None) -> str:
    """
    Get session ID, defaulting to 'default' if available.

    Args:
        session_id: Optional explicit session ID

    Returns:
        The session ID to use

    Raises:
        ValueError: If no session_id provided and no default session available
    """
    if session_id:
        return session_id
    if DEFAULT_SESSION_ID in active_sessions:
        return DEFAULT_SESSION_ID
    raise ValueError(
        "No session_id provided and no default session available. "
        "Set TAIGA_USERNAME/TAIGA_PASSWORD environment variables or use login() tool."
    )


def _get_authenticated_client(session_id: str) -> TaigaClientWrapper:
    """
    Retrieves the authenticated TaigaClientWrapper for a given session ID.
    Raises PermissionError if the session is invalid or not found.
    """
    client = active_sessions.get(session_id)
    # Also check if the client object itself exists and is authenticated
    if not client or not client.is_authenticated:
        logger.warning(
            f"Invalid or expired session ID provided: {session_id[:8] if session_id else 'None'}..."
        )
        # Raise PermissionError - FastMCP will map this to an appropriate error response
        raise PermissionError("Invalid or expired session ID. Please login again.")
    logger.debug(f"Retrieved valid client for session ID: {session_id[:8]}...")
    return client


def _execute_taiga_operation(operation_name: str, operation_callable, error_context: str = ""):
    """
    Execute a Taiga API operation with standardized error handling.

    Args:
        operation_name: Human-readable name of the operation (e.g., "list_projects")
        operation_callable: A callable (lambda or function) that performs the operation
        error_context: Additional context for error messages (e.g., "project 123")

    Returns:
        The result of the operation

    Raises:
        TaigaException: Re-raised from the API
        RuntimeError: Wrapped unexpected errors
    """
    context_str = f" for {error_context}" if error_context else ""
    try:
        result = operation_callable()
        return result
    except TaigaException as e:
        logger.error(f"Taiga API error in {operation_name}{context_str}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in {operation_name}{context_str}: {e}", exc_info=True)
        raise RuntimeError(f"Server error in {operation_name}: {e}")


def _filter_response(response, resource_type: str, verbosity: str = "standard"):
    """
    Filter response fields based on verbosity level.

    Args:
        response: API response (dict, list of dicts, or None)
        resource_type: Type of resource (user_story, task, etc.)
        verbosity: One of 'minimal', 'standard', 'full'

    Returns:
        Filtered response with only requested fields

    Note: 'version' is always included in 'standard' level as it's required
    for update operations (optimistic concurrency control).
    """
    if response is None:
        return None

    # Validate verbosity parameter
    if verbosity not in VALID_VERBOSITY_LEVELS:
        logger.warning(f"Invalid verbosity '{verbosity}', using 'standard'")
        verbosity = "standard"

    if verbosity == "full":
        return response

    if resource_type not in RESPONSE_FIELDS:
        logger.debug(f"No filter config for '{resource_type}', returning full response")
        return response

    fields = RESPONSE_FIELDS[resource_type].get(verbosity)
    if fields is None:
        return response

    field_set = set(fields)

    def filter_dict(d: Dict) -> Dict:
        return {k: v for k, v in d.items() if k in field_set}

    if isinstance(response, list):
        return [filter_dict(item) for item in response]
    return filter_dict(response)


# --- MCP Tools ---


@mcp.tool(
    "get_default_session",
    description="Returns the default session ID if auto-authentication from environment variables was successful.",
)
def get_default_session() -> Dict[str, Any]:
    """
    Returns the default session ID if environment-based authentication was successful.

    Returns:
        Dictionary with session_id if available, or error status.
    """
    if DEFAULT_SESSION_ID in active_sessions:
        client = active_sessions[DEFAULT_SESSION_ID]
        if client and client.is_authenticated:
            return {
                "session_id": DEFAULT_SESSION_ID,
                "status": "active",
                "auto_authenticated": True,
            }
    return {
        "status": "unavailable",
        "message": "No default session. Set TAIGA_USERNAME/TAIGA_PASSWORD environment variables or use login() tool.",
    }


@mcp.tool(
    "login",
    description="Logs into a Taiga instance. Uses environment variables as defaults if parameters not provided.",
)
def login(
    host: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None
) -> Dict[str, str]:
    """
    Handles Taiga login and creates a session.

    Args:
        host: The URL of the Taiga instance. Defaults to TAIGA_API_URL env var.
        username: The Taiga username. Defaults to TAIGA_USERNAME env var.
        password: The Taiga password. Defaults to TAIGA_PASSWORD env var.

    Returns:
        A dictionary containing the session_id upon successful login.
        Example: {"session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}
    """
    # Use env vars as defaults
    actual_host = host or settings.host
    actual_username = username or settings.get_username_value()
    actual_password = password or settings.get_password_value()

    if not actual_host:
        raise ValueError("Host URL required. Set TAIGA_API_URL or provide 'host' parameter.")
    if not actual_username or not actual_password:
        raise ValueError(
            "Credentials required. Set TAIGA_USERNAME/TAIGA_PASSWORD or provide parameters."
        )

    logger.info(f"Executing login tool on host '{actual_host}'")

    try:
        wrapper = TaigaClientWrapper(host=actual_host)
        login_successful = wrapper.login(username=actual_username, password=actual_password)

        if login_successful:
            # Generate a unique session ID
            new_session_id = str(uuid.uuid4())
            # Store the authenticated wrapper in our manual session store
            active_sessions[new_session_id] = wrapper
            logger.info("Login successful. Session created.")
            # Return the session ID to the client
            return {"session_id": new_session_id}
        else:
            # Should not happen if login raises exception on failure, but handle defensively
            logger.error("Login attempt returned False unexpectedly.")
            raise RuntimeError("Login failed for an unknown reason.")

    except (ValueError, TaigaException) as e:
        logger.error(f"Login failed: {e}", exc_info=False)
        # Re-raise the exception - FastMCP will turn it into an error response
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}", exc_info=True)
        raise RuntimeError("An unexpected server error occurred during login.")


# --- Project Tools ---


@mcp.tool(
    "list_projects",
    description="Lists projects accessible to the authenticated user. verbosity: 'minimal' (id/name/slug), 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def list_projects(
    session_id: Optional[str] = None, verbosity: str = "standard"
) -> List[Dict[str, Any]]:
    """Lists projects accessible by the authenticated user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing list_projects for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    result = _execute_taiga_operation(
        "list_projects", lambda: taiga_client_wrapper.api.projects.list()
    )
    return _filter_response(result, "project", verbosity)


@mcp.tool(
    "list_all_projects",
    description="Lists all projects visible to the user (requires admin privileges for full list). verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def list_all_projects(
    session_id: Optional[str] = None, verbosity: str = "standard"
) -> List[Dict[str, Any]]:
    """Lists all projects visible to the authenticated user (scope depends on permissions)."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing list_all_projects for session {actual_session_id[:8]}...")
    # pytaigaclient's list() likely behaves similarly to python-taiga's
    return list_projects(actual_session_id, verbosity)  # Keep delegation


@mcp.tool(
    "get_project",
    description="Gets detailed information about a specific project by its ID. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def get_project(
    project_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Retrieves project details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing get_project ID {project_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "get_project",
        lambda: taiga_client_wrapper.api.projects.get(project_id),
        f"project {project_id}",
    )
    return _filter_response(result, "project", verbosity)


@mcp.tool(
    "get_project_by_slug",
    description="Gets detailed information about a specific project by its slug. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def get_project_by_slug(
    slug: str, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Retrieves project details by slug."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing get_project_by_slug '{slug}' for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "get_project_by_slug",
        lambda: taiga_client_wrapper.api.projects.get(slug=slug),
        f"slug '{slug}'",
    )
    return _filter_response(result, "project", verbosity)


@mcp.tool(
    "create_project",
    description="Creates a new project. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def create_project(
    name: str,
    description: str,
    kwargs: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Creates a new project. Requires name and description. Optional args (e.g., is_private) via kwargs JSON string."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("project", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing create_project '{name}' for session {actual_session_id[:8]} with data: {parsed_kwargs}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not name or not description:
        raise ValueError("Project name and description are required.")

    result = _execute_taiga_operation(
        "create_project",
        lambda: taiga_client_wrapper.api.projects.create(
            name=name, description=description, **parsed_kwargs
        ),
        f"project '{name}'",
    )
    return _filter_response(result, "project", verbosity)


@mcp.tool(
    "update_project",
    description="Updates details of an existing project. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def update_project(
    project_id: int,
    kwargs: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Updates a project. Pass fields to update as kwargs JSON string (e.g., {"name": "New Name", "description": "New Desc"})."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("project", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing update_project ID {project_id} for session {actual_session_id[:8]} with data: {parsed_kwargs}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient update pattern: client.resource.update(id=..., data=...)
        if not parsed_kwargs:
            logger.info(f"No fields provided for update on project {project_id}")
            # Return current state if no updates provided
            result = taiga_client_wrapper.api.projects.get(project_id=project_id)
            return _filter_response(result, "project", verbosity)

        # First fetch the project to get its current version
        current_project = taiga_client_wrapper.api.projects.get(project_id=project_id)
        version = current_project.get("version")
        if not version:
            logger.warning(
                f"Could not determine version for project {project_id}. Attempting update without version."
            )

        # The project update method requires project_id, version, and project_data
        # Use edit() for partial updates (PATCH) instead of update() (PUT)
        updated_project = taiga_client_wrapper.api.projects.edit(
            project_id=project_id, version=version, **parsed_kwargs
        )

        logger.info(f"Project {project_id} update request sent.")
        # Return the result from the update call
        return _filter_response(updated_project, "project", verbosity)
    except TaigaException as e:
        logger.error(f"Taiga API error updating project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error updating project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating project: {e}")


@mcp.tool(
    "delete_project",
    description="Deletes a project by its ID. This is irreversible. Uses default session if session_id not provided.",
)
def delete_project(project_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a project by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(
        f"Executing delete_project ID {project_id} for session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    def do_delete():
        taiga_client_wrapper.api.projects.delete(project_id=project_id)
        return {"status": "deleted", "project_id": project_id}

    return _execute_taiga_operation("delete_project", do_delete, f"project {project_id}")


# --- User Story Tools ---
# Note: get_project_roles, get_*_by_ref functions not implemented - not supported by pytaigaclient


@mcp.tool(
    "list_user_stories",
    description="Lists user stories within a specific project, optionally filtered. verbosity: 'minimal' (id/ref/subject/status/project), 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def list_user_stories(
    project_id: int,
    filters: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> List[Dict[str, Any]]:
    """Lists user stories for a project. Optional filters like 'milestone', 'status', 'assigned_to' can be passed as JSON string."""
    actual_session_id = _get_session_id(session_id)
    parsed_filters = _parse_mcp_kwargs({"filters": filters})
    logger.info(
        f"Executing list_user_stories for project {project_id}, session {actual_session_id[:8]}, filters: {parsed_filters}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "list_user_stories",
        lambda: taiga_client_wrapper.api.user_stories.list(project=project_id, **parsed_filters),
        f"project {project_id}",
    )
    return _filter_response(result, "user_story", verbosity)


@mcp.tool(
    "create_user_story",
    description="Creates a new user story within a project. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def create_user_story(
    project_id: int,
    subject: str,
    kwargs: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Creates a user story. Requires project_id and subject. Optional fields (description, milestone_id, status_id, assigned_to_id, etc.) via kwargs JSON string."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("user_story", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing create_user_story '{subject}' in project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not subject:
        raise ValueError("User story subject cannot be empty.")

    result = _execute_taiga_operation(
        "create_user_story",
        lambda: taiga_client_wrapper.api.user_stories.create(
            project=project_id, subject=subject, **parsed_kwargs
        ),
        f"user story '{subject}'",
    )
    return _filter_response(result, "user_story", verbosity)


@mcp.tool(
    "get_user_story",
    description="Gets detailed information about a specific user story by its ID. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def get_user_story(
    user_story_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Retrieves user story details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_user_story ID {user_story_id} for session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "get_user_story",
        lambda: taiga_client_wrapper.api.user_stories.get(user_story_id),
        f"user story {user_story_id}",
    )
    return _filter_response(result, "user_story", verbosity)


@mcp.tool(
    "update_user_story",
    description="Updates details of an existing user story. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def update_user_story(
    user_story_id: int,
    kwargs: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Updates a user story. Pass fields to update as kwargs JSON string (e.g., {"subject": "New", "status": 2})."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("user_story", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing update_user_story ID {user_story_id} for session {actual_session_id[:8]} with data: {parsed_kwargs}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        if not parsed_kwargs:
            logger.info(f"No fields provided for update on user story {user_story_id}")
            result = taiga_client_wrapper.api.user_stories.get(user_story_id)
            return _filter_response(result, "user_story", verbosity)

        # Get current user story data to retrieve version
        current_story = taiga_client_wrapper.api.user_stories.get(user_story_id)
        version = current_story.get("version")
        if not version:
            logger.warning(
                f"Could not determine version for user story {user_story_id}. Attempting update without version."
            )

        # Use edit method for partial updates with keyword arguments
        updated_story = taiga_client_wrapper.api.user_stories.edit(
            user_story_id=user_story_id, version=version, **parsed_kwargs
        )
        logger.info(f"User story {user_story_id} update request sent.")
        return _filter_response(updated_story, "user_story", verbosity)
    except TaigaException as e:
        logger.error(f"Taiga API error updating user story {user_story_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error updating user story {user_story_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating user story: {e}")


@mcp.tool(
    "delete_user_story",
    description="Deletes a user story by its ID. Uses default session if session_id not provided.",
)
def delete_user_story(user_story_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a user story by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(
        f"Executing delete_user_story ID {user_story_id} for session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    def do_delete():
        taiga_client_wrapper.api.user_stories.delete(user_story_id=user_story_id)
        return {"status": "deleted", "user_story_id": user_story_id}

    return _execute_taiga_operation("delete_user_story", do_delete, f"user story {user_story_id}")


@mcp.tool(
    "assign_user_story_to_user",
    description="Assigns a specific user story to a specific user. Uses default session if session_id not provided.",
)
def assign_user_story_to_user(
    user_story_id: int, user_id: int, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Assigns a user story to a user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing assign_user_story_to_user: US {user_story_id} -> User {user_id}, session {actual_session_id[:8]}..."
    )
    # Delegate to update_user_story with assigned_to
    return update_user_story(user_story_id, json.dumps({"assigned_to": user_id}), actual_session_id)


@mcp.tool(
    "unassign_user_story_from_user",
    description="Unassigns a specific user story (sets assigned user to null). Uses default session if session_id not provided.",
)
def unassign_user_story_from_user(
    user_story_id: int, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Unassigns a user story."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing unassign_user_story_from_user: US {user_story_id}, session {actual_session_id[:8]}..."
    )
    # Delegate to update_user_story with assigned_to=None
    return update_user_story(user_story_id, json.dumps({"assigned_to": None}), actual_session_id)


@mcp.tool(
    "get_user_story_statuses",
    description="Lists the available statuses for user stories within a specific project. Uses default session if session_id not provided.",
)
def get_user_story_statuses(
    project_id: int, session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves the list of user story statuses for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_user_story_statuses for project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    return _execute_taiga_operation(
        "get_user_story_statuses",
        lambda: taiga_client_wrapper.api.userstory_statuses.list(
            query_params={"project": project_id}
        ),
        f"project {project_id}",
    )


# --- Task Tools ---


@mcp.tool(
    "list_tasks",
    description="Lists tasks within a specific project, optionally filtered. verbosity: 'minimal' (id/ref/subject/status/project), 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def list_tasks(
    project_id: int,
    filters: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> List[Dict[str, Any]]:
    """Lists tasks for a project. Optional filters like 'milestone', 'status', 'user_story', 'assigned_to' can be passed as JSON string."""
    actual_session_id = _get_session_id(session_id)
    parsed_filters = _parse_mcp_kwargs({"filters": filters})
    logger.info(
        f"Executing list_tasks for project {project_id}, session {actual_session_id[:8]}, filters: {parsed_filters}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    # Workaround: pytaigaclient Tasks.list has a bug - passes query_params but TaigaClient.get expects params
    # Use the underlying get method directly
    query = {"project": project_id, **parsed_filters}

    result = _execute_taiga_operation(
        "list_tasks",
        lambda: taiga_client_wrapper.api.get("/tasks", params=query),
        f"project {project_id}",
    )
    return _filter_response(result, "task", verbosity)


@mcp.tool(
    "create_task",
    description="Creates a new task within a project. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def create_task(
    project_id: int,
    subject: str,
    kwargs: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Creates a task. Requires project_id and subject. Optional fields (description, milestone_id, status_id, user_story_id, assigned_to_id, etc.) via kwargs JSON string."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("task", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing create_task '{subject}' in project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not subject:
        raise ValueError("Task subject cannot be empty.")

    result = _execute_taiga_operation(
        "create_task",
        lambda: taiga_client_wrapper.api.tasks.create(
            project=project_id, subject=subject, data=parsed_kwargs if parsed_kwargs else None
        ),
        f"task '{subject}'",
    )
    return _filter_response(result, "task", verbosity)


@mcp.tool(
    "get_task",
    description="Gets detailed information about a specific task by its ID. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def get_task(
    task_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Retrieves task details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing get_task ID {task_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "get_task", lambda: taiga_client_wrapper.api.tasks.get(task_id), f"task {task_id}"
    )
    return _filter_response(result, "task", verbosity)


@mcp.tool(
    "update_task",
    description="Updates details of an existing task. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def update_task(
    task_id: int, kwargs: Any = None, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Updates a task. Pass fields to update as kwargs JSON string (e.g., {"subject": "New", "status": 2})."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("task", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing update_task ID {task_id} for session {actual_session_id[:8]} with data: {parsed_kwargs}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient edit pattern for partial updates
        if not parsed_kwargs:
            logger.info(f"No fields provided for update on task {task_id}")
            result = taiga_client_wrapper.api.tasks.get(task_id)
            return _filter_response(result, "task", verbosity)

        # Get current task data to retrieve version
        current_task = taiga_client_wrapper.api.tasks.get(task_id)
        version = current_task.get("version")
        if not version:
            raise ValueError(f"Could not determine version for task {task_id}")

        # Use edit method for partial updates - pytaigaclient uses data: Dict not **kwargs
        updated_task = taiga_client_wrapper.api.tasks.edit(
            task_id=task_id, version=version, data=parsed_kwargs
        )
        logger.info(f"Task {task_id} update request sent.")
        return _filter_response(updated_task, "task", verbosity)
    except TaigaException as e:
        logger.error(f"Taiga API error updating task {task_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error updating task {task_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating task: {e}")


@mcp.tool(
    "delete_task",
    description="Deletes a task by its ID. Uses default session if session_id not provided.",
)
def delete_task(task_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a task by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(f"Executing delete_task ID {task_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    def do_delete():
        taiga_client_wrapper.api.tasks.delete(task_id=task_id)
        return {"status": "deleted", "task_id": task_id}

    return _execute_taiga_operation("delete_task", do_delete, f"task {task_id}")


@mcp.tool(
    "assign_task_to_user",
    description="Assigns a specific task to a specific user. Uses default session if session_id not provided.",
)
def assign_task_to_user(
    task_id: int, user_id: int, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Assigns a task to a user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing assign_task_to_user: Task {task_id} -> User {user_id}, session {actual_session_id[:8]}..."
    )
    # Delegate to update_task with assigned_to
    return update_task(task_id, json.dumps({"assigned_to": user_id}), actual_session_id)


@mcp.tool(
    "unassign_task_from_user",
    description="Unassigns a specific task (sets assigned user to null). Uses default session if session_id not provided.",
)
def unassign_task_from_user(task_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Unassigns a task."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing unassign_task_from_user: Task {task_id}, session {actual_session_id[:8]}..."
    )
    # Delegate to update_task with assigned_to=None
    return update_task(task_id, json.dumps({"assigned_to": None}), actual_session_id)


@mcp.tool(
    "get_task_statuses",
    description="Lists the available statuses for tasks within a specific project. Uses default session if session_id not provided.",
)
def get_task_statuses(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of task statuses for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_task_statuses for project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    return _execute_taiga_operation(
        "get_task_statuses",
        lambda: taiga_client_wrapper.api.task_statuses.list(query_params={"project": project_id}),
        f"project {project_id}",
    )


# --- Issue Tools ---


@mcp.tool(
    "list_issues",
    description="Lists issues within a specific project, optionally filtered. verbosity: 'minimal' (id/ref/subject/status/priority/severity/project), 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def list_issues(
    project_id: int,
    filters: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> List[Dict[str, Any]]:
    """Lists issues for a project. Optional filters like 'milestone', 'status', 'priority', 'severity', 'type', 'assigned_to' can be passed as JSON string."""
    actual_session_id = _get_session_id(session_id)
    parsed_filters = _parse_mcp_kwargs({"filters": filters})
    logger.info(
        f"Executing list_issues for project {project_id}, session {actual_session_id[:8]}, filters: {parsed_filters}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    query = {"project": project_id, **parsed_filters}

    result = _execute_taiga_operation(
        "list_issues",
        lambda: taiga_client_wrapper.api.issues.list(query_params=query),
        f"project {project_id}",
    )
    return _filter_response(result, "issue", verbosity)


@mcp.tool(
    "create_issue",
    description="Creates a new issue within a project. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def create_issue(
    project_id: int,
    subject: str,
    priority_id: int,
    status_id: int,
    severity_id: int,
    type_id: int,
    kwargs: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Creates an issue. Requires project_id, subject, priority_id, status_id, severity_id, type_id. Optional fields (description, assigned_to_id, etc.) via kwargs JSON string."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("issue", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing create_issue '{subject}' in project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not subject:
        raise ValueError("Issue subject cannot be empty.")

    issue_data = {
        "priority": priority_id,
        "status": status_id,
        "type": type_id,
        "severity": severity_id,
        **parsed_kwargs,
    }

    result = _execute_taiga_operation(
        "create_issue",
        lambda: taiga_client_wrapper.api.issues.create(
            project=project_id, subject=subject, data=issue_data
        ),
        f"issue '{subject}'",
    )
    return _filter_response(result, "issue", verbosity)


@mcp.tool(
    "get_issue",
    description="Gets detailed information about a specific issue by its ID. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def get_issue(
    issue_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Retrieves issue details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing get_issue ID {issue_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "get_issue",
        lambda: taiga_client_wrapper.api.issues.get(issue_id),
        f"issue {issue_id}",
    )
    return _filter_response(result, "issue", verbosity)


@mcp.tool(
    "update_issue",
    description="Updates details of an existing issue. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def update_issue(
    issue_id: int, kwargs: Any = None, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Updates an issue. Pass fields to update as kwargs JSON string (e.g., {"subject": "New", "status": 2})."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("issue", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing update_issue ID {issue_id} for session {actual_session_id[:8]} with data: {parsed_kwargs}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient edit pattern for partial updates
        if not parsed_kwargs:
            logger.info(f"No fields provided for update on issue {issue_id}")
            result = taiga_client_wrapper.api.issues.get(issue_id)
            return _filter_response(result, "issue", verbosity)

        # Get current issue data to retrieve version
        current_issue = taiga_client_wrapper.api.issues.get(issue_id)
        version = current_issue.get("version")
        if not version:
            raise ValueError(f"Could not determine version for issue {issue_id}")

        # Use edit method for partial updates - pytaigaclient uses data: Dict not **kwargs
        updated_issue = taiga_client_wrapper.api.issues.edit(
            issue_id=issue_id, version=version, data=parsed_kwargs
        )
        logger.info(f"Issue {issue_id} update request sent.")
        return _filter_response(updated_issue, "issue", verbosity)
    except TaigaException as e:
        logger.error(f"Taiga API error updating issue {issue_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error updating issue {issue_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating issue: {e}")


@mcp.tool(
    "delete_issue",
    description="Deletes an issue by its ID. Uses default session if session_id not provided.",
)
def delete_issue(issue_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes an issue by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(f"Executing delete_issue ID {issue_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    def do_delete():
        taiga_client_wrapper.api.issues.delete(issue_id=issue_id)
        return {"status": "deleted", "issue_id": issue_id}

    return _execute_taiga_operation("delete_issue", do_delete, f"issue {issue_id}")


@mcp.tool(
    "assign_issue_to_user",
    description="Assigns a specific issue to a specific user. Uses default session if session_id not provided.",
)
def assign_issue_to_user(
    issue_id: int, user_id: int, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Assigns an issue to a user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing assign_issue_to_user: Issue {issue_id} -> User {user_id}, session {actual_session_id[:8]}..."
    )
    # Delegate to update_issue with assigned_to
    return update_issue(issue_id, json.dumps({"assigned_to": user_id}), actual_session_id)


@mcp.tool(
    "unassign_issue_from_user",
    description="Unassigns a specific issue (sets assigned user to null). Uses default session if session_id not provided.",
)
def unassign_issue_from_user(issue_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Unassigns an issue."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing unassign_issue_from_user: Issue {issue_id}, session {actual_session_id[:8]}..."
    )
    # Delegate to update_issue with assigned_to=None
    return update_issue(issue_id, json.dumps({"assigned_to": None}), actual_session_id)


@mcp.tool(
    "get_issue_statuses",
    description="Lists the available statuses for issues within a specific project. Uses default session if session_id not provided.",
)
def get_issue_statuses(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of issue statuses for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_issue_statuses for project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    return _execute_taiga_operation(
        "get_issue_statuses",
        lambda: taiga_client_wrapper.api.issue_statuses.list(query_params={"project": project_id}),
        f"project {project_id}",
    )


@mcp.tool(
    "get_issue_priorities",
    description="Lists the available priorities for issues within a specific project. Uses default session if session_id not provided.",
)
def get_issue_priorities(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of issue priorities for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_issue_priorities for project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    return _execute_taiga_operation(
        "get_issue_priorities",
        lambda: taiga_client_wrapper.api.get("/priorities", params={"project": project_id}),
        f"project {project_id}",
    )


@mcp.tool(
    "get_issue_severities",
    description="Lists the available severities for issues within a specific project. Uses default session if session_id not provided.",
)
def get_issue_severities(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of issue severities for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_issue_severities for project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    return _execute_taiga_operation(
        "get_issue_severities",
        lambda: taiga_client_wrapper.api.get("/severities", params={"project": project_id}),
        f"project {project_id}",
    )


@mcp.tool(
    "get_issue_types",
    description="Lists the available types for issues within a specific project. Uses default session if session_id not provided.",
)
def get_issue_types(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of issue types for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_issue_types for project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    return _execute_taiga_operation(
        "get_issue_types",
        lambda: taiga_client_wrapper.api.issue_types.list(query_params={"project": project_id}),
        f"project {project_id}",
    )


# --- Epic Tools ---


@mcp.tool(
    "list_epics",
    description="Lists epics within a specific project, optionally filtered. verbosity: 'minimal' (id/ref/subject/status/project), 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def list_epics(
    project_id: int,
    filters: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> List[Dict[str, Any]]:
    """Lists epics for a project. Optional filters like 'status', 'assigned_to' can be passed as JSON string."""
    actual_session_id = _get_session_id(session_id)
    parsed_filters = _parse_mcp_kwargs({"filters": filters})
    logger.info(
        f"Executing list_epics for project {project_id}, session {actual_session_id[:8]}, filters: {parsed_filters}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    query = {"project": project_id, **parsed_filters}

    result = _execute_taiga_operation(
        "list_epics",
        lambda: taiga_client_wrapper.api.epics.list(query_params=query),
        f"project {project_id}",
    )
    return _filter_response(result, "epic", verbosity)


@mcp.tool(
    "create_epic",
    description="Creates a new epic within a project. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def create_epic(
    project_id: int,
    subject: str,
    kwargs: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Creates an epic. Requires project_id and subject. Optional fields (description, status_id, assigned_to_id, color, etc.) via kwargs JSON string."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("epic", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing create_epic '{subject}' in project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not subject:
        raise ValueError("Epic subject cannot be empty.")

    result = _execute_taiga_operation(
        "create_epic",
        lambda: taiga_client_wrapper.api.epics.create(
            project=project_id, subject=subject, **parsed_kwargs
        ),
        f"epic '{subject}'",
    )
    return _filter_response(result, "epic", verbosity)


@mcp.tool(
    "get_epic",
    description="Gets detailed information about a specific epic by its ID. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def get_epic(
    epic_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Retrieves epic details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing get_epic ID {epic_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "get_epic", lambda: taiga_client_wrapper.api.epics.get(epic_id), f"epic {epic_id}"
    )
    return _filter_response(result, "epic", verbosity)


@mcp.tool(
    "update_epic",
    description="Updates details of an existing epic. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def update_epic(
    epic_id: int, kwargs: Any = None, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Updates an epic. Pass fields to update as kwargs JSON string (e.g., {"subject": "New", "color": "#FF0000"})."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("epic", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing update_epic ID {epic_id} for session {actual_session_id[:8]} with data: {parsed_kwargs}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        if not parsed_kwargs:
            logger.info(f"No fields provided for update on epic {epic_id}")
            result = taiga_client_wrapper.api.epics.get(epic_id)
            return _filter_response(result, "epic", verbosity)

        # Get current epic data to retrieve version
        current_epic = taiga_client_wrapper.api.epics.get(epic_id)
        version = current_epic.get("version")
        if not version:
            raise ValueError(f"Could not determine version for epic {epic_id}")

        # Use edit method for partial updates with keyword arguments
        updated_epic = taiga_client_wrapper.api.epics.edit(
            epic_id=epic_id, version=version, **parsed_kwargs
        )
        logger.info(f"Epic {epic_id} update request sent.")
        return _filter_response(updated_epic, "epic", verbosity)
    except TaigaException as e:
        logger.error(f"Taiga API error updating epic {epic_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error updating epic {epic_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating epic: {e}")


@mcp.tool(
    "delete_epic",
    description="Deletes an epic by its ID. Uses default session if session_id not provided.",
)
def delete_epic(epic_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes an epic by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(f"Executing delete_epic ID {epic_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    def do_delete():
        taiga_client_wrapper.api.epics.delete(epic_id=epic_id)
        return {"status": "deleted", "epic_id": epic_id}

    return _execute_taiga_operation("delete_epic", do_delete, f"epic {epic_id}")


@mcp.tool(
    "assign_epic_to_user",
    description="Assigns a specific epic to a specific user. Uses default session if session_id not provided.",
)
def assign_epic_to_user(
    epic_id: int, user_id: int, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Assigns an epic to a user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing assign_epic_to_user: Epic {epic_id} -> User {user_id}, session {actual_session_id[:8]}..."
    )
    # Delegate to update_epic with assigned_to
    return update_epic(epic_id, json.dumps({"assigned_to": user_id}), actual_session_id)


@mcp.tool(
    "unassign_epic_from_user",
    description="Unassigns a specific epic (sets assigned user to null). Uses default session if session_id not provided.",
)
def unassign_epic_from_user(epic_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Unassigns an epic."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing unassign_epic_from_user: Epic {epic_id}, session {actual_session_id[:8]}..."
    )
    # Delegate to update_epic with assigned_to=None
    return update_epic(epic_id, json.dumps({"assigned_to": None}), actual_session_id)


@mcp.tool(
    "link_user_story_to_epic",
    description="Links a User Story to an Epic. Uses default session if session_id not provided.",
)
def link_user_story_to_epic(
    epic_id: int, user_story_id: int, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Links a user story to an epic."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing link_user_story_to_epic: Epic {epic_id} <- Story {user_story_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    def do_link():
        # Direct API call to ensure correct endpoint and payload
        # Correct endpoint: /epics/{epic_id}/related_userstories (no underscore in userstories)
        # Payload must include 'epic' ID and 'user_story' ID
        # Using 'json' kwarg as this is standard for requests/client wrappers
        taiga_client_wrapper.api.post(
            f"/epics/{epic_id}/related_userstories",
            json={"epic": epic_id, "user_story": user_story_id},
        )
        return {
            "status": "linked",
            "epic_id": epic_id,
            "user_story_id": user_story_id,
        }

    return _execute_taiga_operation(
        "link_user_story_to_epic", do_link, f"link story {user_story_id} to epic {epic_id}"
    )


# --- Milestone (Sprint) Tools ---


@mcp.tool(
    "list_milestones",
    description="Lists milestones (sprints) within a specific project. verbosity: 'minimal' (id/name/slug/project), 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def list_milestones(
    project_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> List[Dict[str, Any]]:
    """Lists milestones for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing list_milestones for project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "list_milestones",
        lambda: taiga_client_wrapper.api.milestones.list(project=project_id),
        f"project {project_id}",
    )
    return _filter_response(result, "milestone", verbosity)


@mcp.tool(
    "create_milestone",
    description="Creates a new milestone (sprint) within a project. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def create_milestone(
    project_id: int,
    name: str,
    estimated_start: str,
    estimated_finish: str,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Creates a milestone. Requires project_id, name, estimated_start (YYYY-MM-DD), and estimated_finish (YYYY-MM-DD)."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing create_milestone '{name}' in project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not all([name, estimated_start, estimated_finish]):
        raise ValueError("Milestone requires name, estimated_start, and estimated_finish.")

    result = _execute_taiga_operation(
        "create_milestone",
        lambda: taiga_client_wrapper.api.milestones.create(
            project=project_id,
            name=name,
            estimated_start=estimated_start,
            estimated_finish=estimated_finish,
        ),
        f"milestone '{name}'",
    )
    return _filter_response(result, "milestone", verbosity)


@mcp.tool(
    "get_milestone",
    description="Gets detailed information about a specific milestone by its ID. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def get_milestone(
    milestone_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Retrieves milestone details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing get_milestone ID {milestone_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "get_milestone",
        lambda: taiga_client_wrapper.api.milestones.get(milestone_id),
        f"milestone {milestone_id}",
    )
    return _filter_response(result, "milestone", verbosity)


@mcp.tool(
    "update_milestone",
    description="Updates details of an existing milestone. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def update_milestone(
    milestone_id: int,
    kwargs: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Updates a milestone. Pass fields to update as kwargs JSON string (e.g., {"name": "Sprint 2", "estimated_finish": "2025-02-28"})."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("milestone", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing update_milestone ID {milestone_id} for session {actual_session_id[:8]} with data: {parsed_kwargs}"
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        if not parsed_kwargs:
            logger.info(f"No fields provided for update on milestone {milestone_id}")
            result = taiga_client_wrapper.api.milestones.get(milestone_id)
            return _filter_response(result, "milestone", verbosity)

        # Get current milestone data to retrieve version
        current_milestone = taiga_client_wrapper.api.milestones.get(milestone_id)
        version = current_milestone.get("version")
        if not version:
            logger.warning(
                f"Could not determine version for milestone {milestone_id}. Attempting update without version."
            )

        # Use edit method for partial updates with keyword arguments
        updated_milestone = taiga_client_wrapper.api.milestones.edit(
            milestone_id=milestone_id, version=version, **parsed_kwargs
        )
        logger.info(f"Milestone {milestone_id} update request sent.")
        return _filter_response(updated_milestone, "milestone", verbosity)
    except TaigaException as e:
        logger.error(f"Taiga API error updating milestone {milestone_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error updating milestone {milestone_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating milestone: {e}")


@mcp.tool(
    "delete_milestone",
    description="Deletes a milestone by its ID. Uses default session if session_id not provided.",
)
def delete_milestone(milestone_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a milestone by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(
        f"Executing delete_milestone ID {milestone_id} for session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    def do_delete():
        taiga_client_wrapper.api.milestones.delete(milestone_id=milestone_id)
        return {"status": "deleted", "milestone_id": milestone_id}

    return _execute_taiga_operation("delete_milestone", do_delete, f"milestone {milestone_id}")


# --- User Management Tools ---


@mcp.tool(
    "get_project_members",
    description="Lists members of a specific project. verbosity: 'minimal' (id/user/full_name), 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def get_project_members(
    project_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> List[Dict[str, Any]]:
    """Retrieves the list of members for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_project_members for project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "get_project_members",
        lambda: taiga_client_wrapper.api.memberships.list(query_params={"project": project_id}),
        f"project {project_id}",
    )
    return _filter_response(result, "member", verbosity)


@mcp.tool(
    "invite_project_user",
    description="Invites a user to a project by email with a specific role. Uses default session if session_id not provided.",
)
def invite_project_user(
    project_id: int, email: str, role_id: int, session_id: Optional[str] = None
) -> Dict[str, Any]:
    """Invites a user via email to join the project with the specified role ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing invite_project_user {email} to project {project_id} (role {role_id}), session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not email:
        raise ValueError("Email cannot be empty.")

    def do_invite():
        result = taiga_client_wrapper.api.memberships.invite(
            project=project_id, email=email, role_id=role_id
        )
        return (
            result
            if isinstance(result, dict)
            else {"status": "invited", "email": email, "details": result}
        )

    return _execute_taiga_operation(
        "invite_project_user", do_invite, f"email '{email}' to project {project_id}"
    )


# --- Wiki Tools ---


@mcp.tool(
    "list_wiki_pages",
    description="Lists wiki pages within a specific project. verbosity: 'minimal' (id/slug/project), 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def list_wiki_pages(
    project_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> List[Dict[str, Any]]:
    """Lists wiki pages for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing list_wiki_pages for project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "list_wiki_pages",
        lambda: taiga_client_wrapper.api.wiki.list(query_params={"project": project_id}),
        f"project {project_id}",
    )
    return _filter_response(result, "wiki_page", verbosity)


@mcp.tool(
    "get_wiki_page",
    description="Gets a specific wiki page by its ID. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def get_wiki_page(
    wiki_page_id: int, session_id: Optional[str] = None, verbosity: str = "standard"
) -> Dict[str, Any]:
    """Retrieves wiki page details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing get_wiki_page ID {wiki_page_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)

    result = _execute_taiga_operation(
        "get_wiki_page",
        lambda: taiga_client_wrapper.api.wiki.get(wiki_page_id),
        f"wiki page {wiki_page_id}",
    )
    return _filter_response(result, "wiki_page", verbosity)


@mcp.tool(
    "create_wiki_page",
    description="Creates a new wiki page. verbosity: 'minimal', 'standard' (default), 'full'. Uses default session if session_id not provided.",
)
def create_wiki_page(
    project_id: int,
    slug: str,
    content: str,
    kwargs: Any = None,
    session_id: Optional[str] = None,
    verbosity: str = "standard",
) -> Dict[str, Any]:
    """Creates a wiki page. Requires project_id, slug, and content."""
    actual_session_id = _get_session_id(session_id)
    parsed_kwargs = _validate_kwargs("wiki_page", _parse_mcp_kwargs({"kwargs": kwargs}))
    logger.info(
        f"Executing create_wiki_page '{slug}' in project {project_id}, session {actual_session_id[:8]}..."
    )
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not slug or not content:
        raise ValueError("Wiki page slug and content are required.")

    result = _execute_taiga_operation(
        "create_wiki_page",
        lambda: taiga_client_wrapper.api.wiki.create(
            project=project_id, slug=slug, content=content, **parsed_kwargs
        ),
        f"wiki page '{slug}'",
    )
    return _filter_response(result, "wiki_page", verbosity)


# --- Session Management Tools ---


@mcp.tool(
    "logout",
    description="Invalidates the current session_id. Uses default session if session_id not provided.",
)
def logout(session_id: Optional[str] = None) -> Dict[str, Any]:
    """Logs out the current session, invalidating the session_id."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing logout for session {actual_session_id[:8]}...")
    # Remove from dict, return None if not found
    client_wrapper = active_sessions.pop(actual_session_id, None)
    if client_wrapper:
        logger.info(f"Session {actual_session_id[:8]} logged out successfully.")
        # No specific API logout call needed usually for token-based auth
        return {"status": "logged_out", "session_id": actual_session_id}
    else:
        logger.warning(f"Attempted to log out non-existent session: {actual_session_id[:8]}")
        return {"status": "session_not_found", "session_id": actual_session_id}


@mcp.tool(
    "session_status",
    description="Checks if the provided session_id is currently active and valid. Uses default session if session_id not provided.",
)
def session_status(session_id: Optional[str] = None) -> Dict[str, Any]:
    """Checks the validity of the current session_id."""
    actual_session_id = _get_session_id(session_id)
    logger.debug(f"Executing session_status check for session {actual_session_id[:8]}...")
    client_wrapper = active_sessions.get(actual_session_id)
    if client_wrapper and client_wrapper.is_authenticated:
        try:
            # Use pytaigaclient users.get_me() call
            me = client_wrapper.api.users.get_me()
            # Extract username from the returned dict
            username = me.get("username", "Unknown")
            logger.debug(f"Session {actual_session_id[:8]} is active for user {username}.")
            return {"status": "active", "session_id": actual_session_id, "username": username}
        except TaigaException:
            logger.warning(
                f"Session {actual_session_id[:8]} found but token seems invalid (API check failed)."
            )
            # Clean up invalid session
            active_sessions.pop(actual_session_id, None)
            return {
                "status": "inactive",
                "reason": "token_invalid",
                "session_id": actual_session_id,
            }
        except Exception as e:  # Catch broader exceptions during the 'me' call
            logger.error(
                f"Unexpected error during session status check for {actual_session_id[:8]}: {e}",
                exc_info=True,
            )
            # Return a distinct status for unexpected errors during check
            return {"status": "error", "reason": "check_failed", "session_id": actual_session_id}
    elif (
        client_wrapper
    ):  # Client exists but not authenticated (shouldn't happen with current login logic)
        logger.warning(
            f"Session {actual_session_id[:8]} exists but client wrapper is not authenticated."
        )
        return {
            "status": "inactive",
            "reason": "not_authenticated",
            "session_id": actual_session_id,
        }
    else:  # Session ID not found
        logger.debug(f"Session {actual_session_id[:8]} not found.")
        return {"status": "inactive", "reason": "not_found", "session_id": actual_session_id}


# --- Run the server ---
if __name__ == "__main__":
    mcp.run()
