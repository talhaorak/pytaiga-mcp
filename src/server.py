# server.py
import json
import logging
import logging.config
import uuid
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, AsyncIterator

from mcp.server.fastmcp import FastMCP
from pytaigaclient.exceptions import TaigaException

# Assuming taiga_client.py is in the same directory or accessible via PYTHONPATH
from src.taiga_client import TaigaClientWrapper
from src.config import settings, mask_credential

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Log to stderr by default
    ]
)
logger = logging.getLogger(__name__)
# Quiet down pytaigaclient library logging if needed
logging.getLogger("pytaigaclient").setLevel(logging.WARNING)

# --- Helper Functions ---

def _parse_mcp_kwargs(kwargs: dict) -> dict:
    """Parse MCP kwargs which may be passed as a JSON string.

    When FastMCP receives **kwargs in a tool function, it may pass
    additional parameters as a JSON string under the 'kwargs' key.
    This function handles that case and returns a proper dict.
    """
    if not kwargs:
        return {}
    # If kwargs contains a single 'kwargs' key with a string value, parse it
    if len(kwargs) == 1 and 'kwargs' in kwargs:
        kwargs_val = kwargs['kwargs']
        if isinstance(kwargs_val, str):
            return json.loads(kwargs_val) if kwargs_val else {}
        return kwargs_val if isinstance(kwargs_val, dict) else {}
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
                username=settings.get_username_value(),
                password=settings.get_password_value()
            )
            if success:
                active_sessions[DEFAULT_SESSION_ID] = wrapper
                logger.info(f"Auto-authentication successful. Default session created: '{DEFAULT_SESSION_ID}'")
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
mcp = FastMCP(
    "Taiga Bridge",
    dependencies=["pytaigaclient"],
    lifespan=server_lifespan
)

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
        logger.warning(f"Invalid or expired session ID provided: {session_id[:8] if session_id else 'None'}...")
        # Raise PermissionError - FastMCP will map this to an appropriate error response
        raise PermissionError(
            f"Invalid or expired session ID. Please login again.")
    logger.debug(f"Retrieved valid client for session ID: {session_id[:8]}...")
    return client

# --- MCP Tools ---


@mcp.tool("get_default_session", description="Returns the default session ID if auto-authentication from environment variables was successful.")
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
                "auto_authenticated": True
            }
    return {
        "status": "unavailable",
        "message": "No default session. Set TAIGA_USERNAME/TAIGA_PASSWORD environment variables or use login() tool."
    }


@mcp.tool("login", description="Logs into a Taiga instance. Uses environment variables as defaults if parameters not provided.")
def login(
    host: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None
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

@mcp.tool("list_projects", description="Lists projects accessible to the authenticated user. Uses default session if session_id not provided.")
def list_projects(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists projects accessible by the authenticated user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing list_projects for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.method()
        projects = taiga_client_wrapper.api.projects.list()
        # Remove .to_dict() as pytaigaclient should return dicts
        # result = [p.to_dict() for p in projects]
        logger.info(
            f"list_projects successful for session {actual_session_id[:8]}, found {len(projects)} projects.")
        return projects # Return directly
    except TaigaException as e:
        logger.error(f"Taiga API error listing projects: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error listing projects: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing projects: {e}")


@mcp.tool("list_all_projects", description="Lists all projects visible to the user (requires admin privileges for full list). Uses default session if session_id not provided.")
def list_all_projects(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists all projects visible to the authenticated user (scope depends on permissions)."""
    actual_session_id = _get_session_id(session_id)
    logger.info(f"Executing list_all_projects for session {actual_session_id[:8]}...")
    # pytaigaclient's list() likely behaves similarly to python-taiga's
    return list_projects(actual_session_id) # Keep delegation


@mcp.tool("get_project", description="Gets detailed information about a specific project by its ID. Uses default session if session_id not provided.")
def get_project(project_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves project details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_project ID {project_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.get(project_id)
        project = taiga_client_wrapper.api.projects.get(project_id)
        # return project.to_dict() # Remove .to_dict()
        return project # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting project: {e}")


@mcp.tool("get_project_by_slug", description="Gets detailed information about a specific project by its slug. Uses default session if session_id not provided.")
def get_project_by_slug(slug: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves project details by slug."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_project_by_slug '{slug}' for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.get(slug=...)
        project = taiga_client_wrapper.api.projects.get(slug=slug)
        # return project.to_dict() # Remove .to_dict()
        return project # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting project by slug '{slug}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting project by slug '{slug}': {e}", exc_info=True)
        raise RuntimeError(f"Server error getting project by slug: {e}")


@mcp.tool("create_project", description="Creates a new project. Uses default session if session_id not provided.")
def create_project(name: str, description: str, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Creates a new project. Requires name and description. Optional args (e.g., is_private) via kwargs."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing create_project '{name}' for session {actual_session_id[:8]} with data: {kwargs}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    if not name or not description:
        raise ValueError("Project name and description are required.")
    try:
        # Use pytaigaclient syntax: client.projects.create(name=..., description=..., **kwargs)
        new_project = taiga_client_wrapper.api.projects.create(
            name=name, description=description, **kwargs
        )
        logger.info(f"Project '{name}' created successfully (ID: {new_project.get('id', 'N/A')}).")
        return new_project # Return the created project dict
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating project '{name}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating project '{name}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating project: {e}")


@mcp.tool("update_project", description="Updates details of an existing project. Uses default session if session_id not provided.")
def update_project(project_id: int, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Updates a project. Pass fields to update as keyword arguments (e.g., name='New Name', description='New Desc')."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing update_project ID {project_id} for session {actual_session_id[:8]} with data: {kwargs}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    try:
        # Use pytaigaclient update pattern: client.resource.update(id=..., data=...)
        if not kwargs:
             logger.info(f"No fields provided for update on project {project_id}")
             # Return current state if no updates provided
             return taiga_client_wrapper.api.projects.get(project_id=project_id)

        # First fetch the project to get its current version
        current_project = taiga_client_wrapper.api.projects.get(project_id=project_id)
        version = current_project.get('version')
        if not version:
            raise ValueError(f"Could not determine version for project {project_id}")
            
        # The project update method requires project_id, version, and project_data
        updated_project = taiga_client_wrapper.api.projects.update(
            project_id=project_id, 
            version=version, 
            project_data=kwargs
        )
        logger.info(f"Project {project_id} update request sent.")
        # Return the result from the update call
        return updated_project
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating project: {e}")


@mcp.tool("delete_project", description="Deletes a project by its ID. This is irreversible. Uses default session if session_id not provided.")
def delete_project(project_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a project by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(
        f"Executing delete_project ID {project_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # pytaigaclient uses named args matching the parameter (e.g., project_id, not id)
        taiga_client_wrapper.api.projects.delete(project_id=project_id)
        logger.info(f"Project {project_id} deleted successfully.")
        return {"status": "deleted", "project_id": project_id}
    except TaigaException as e:
        logger.error(
            f"Taiga API error deleting project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error deleting project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error deleting project: {e}")


# --- User Story Tools ---
# Note: get_project_roles, get_*_by_ref functions not implemented - not supported by pytaigaclient

@mcp.tool("list_user_stories", description="Lists user stories within a specific project, optionally filtered. Uses default session if session_id not provided.")
def list_user_stories(project_id: int, session_id: Optional[str] = None, **filters) -> List[Dict[str, Any]]:
    """Lists user stories for a project. Optional filters like 'milestone', 'status', 'assigned_to' can be passed as keyword arguments."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing list_user_stories for project {project_id}, session {actual_session_id[:8]}, filters: {filters}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(project=..., **filters)
        stories = taiga_client_wrapper.api.user_stories.list(project=project_id, **filters)
        # return [s.to_dict() for s in stories] # Remove .to_dict()
        return stories # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing user stories for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing user stories for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing user stories: {e}")


@mcp.tool("create_user_story", description="Creates a new user story within a project. Uses default session if session_id not provided.")
def create_user_story(project_id: int, subject: str, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Creates a user story. Requires project_id and subject. Optional fields (description, milestone_id, status_id, assigned_to_id, etc.) via kwargs."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing create_user_story '{subject}' in project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    if not subject:
        raise ValueError("User story subject cannot be empty.")
    try:
        # Use pytaigaclient syntax: client.resource.create(project=..., subject=..., **kwargs)
        story = taiga_client_wrapper.api.user_stories.create(
            project=project_id, subject=subject, **kwargs)
        logger.info(
            f"User story '{subject}' created successfully (ID: {story.get('id', 'N/A')}).") # Use .get() for safety
        # return story.to_dict() # Remove .to_dict()
        return story # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating user story '{subject}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating user story '{subject}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating user story: {e}")


@mcp.tool("get_user_story", description="Gets detailed information about a specific user story by its ID. Uses default session if session_id not provided.")
def get_user_story(user_story_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves user story details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_user_story ID {user_story_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # User stories expects user_story_id as a positional argument
        story = taiga_client_wrapper.api.user_stories.get(user_story_id)
        # return story.to_dict() # Remove .to_dict()
        return story # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting user story {user_story_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting user story {user_story_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting user story: {e}")


@mcp.tool("update_user_story", description="Updates details of an existing user story. Uses default session if session_id not provided.")
def update_user_story(user_story_id: int, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Updates a user story. Pass fields to update as keyword arguments (e.g., subject, description, status_id, assigned_to)."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing update_user_story ID {user_story_id} for session {actual_session_id[:8]} with data: {kwargs}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    try:
        if not kwargs:
             logger.info(f"No fields provided for update on user story {user_story_id}")
             return taiga_client_wrapper.api.user_stories.get(user_story_id)

        # Get current user story data to retrieve version
        current_story = taiga_client_wrapper.api.user_stories.get(user_story_id)
        version = current_story.get('version')
        if not version:
            raise ValueError(f"Could not determine version for user story {user_story_id}")
            
        # Use edit method for partial updates with keyword arguments
        updated_story = taiga_client_wrapper.api.user_stories.edit(
            user_story_id=user_story_id,
            version=version,
            **kwargs
        )
        logger.info(f"User story {user_story_id} update request sent.")
        return updated_story
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating user story {user_story_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating user story {user_story_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating user story: {e}")


@mcp.tool("delete_user_story", description="Deletes a user story by its ID. Uses default session if session_id not provided.")
def delete_user_story(user_story_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a user story by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(
        f"Executing delete_user_story ID {user_story_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # pytaigaclient uses named args matching the parameter (e.g., user_story_id, not id)
        taiga_client_wrapper.api.user_stories.delete(user_story_id=user_story_id)
        logger.info(f"User story {user_story_id} deleted successfully.")
        return {"status": "deleted", "user_story_id": user_story_id}
    except TaigaException as e:
        logger.error(
            f"Taiga API error deleting user story {user_story_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error deleting user story {user_story_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error deleting user story: {e}")


@mcp.tool("assign_user_story_to_user", description="Assigns a specific user story to a specific user. Uses default session if session_id not provided.")
def assign_user_story_to_user(user_story_id: int, user_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Assigns a user story to a user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing assign_user_story_to_user: US {user_story_id} -> User {user_id}, session {actual_session_id[:8]}...")
    # Delegate to update_user_story, assuming 'assigned_to' key works
    return update_user_story(user_story_id, actual_session_id, assigned_to=user_id)


@mcp.tool("unassign_user_story_from_user", description="Unassigns a specific user story (sets assigned user to null). Uses default session if session_id not provided.")
def unassign_user_story_from_user(user_story_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Unassigns a user story."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing unassign_user_story_from_user: US {user_story_id}, session {actual_session_id[:8]}...")
    # Delegate to update_user_story with assigned_to=None
    return update_user_story(user_story_id, actual_session_id, assigned_to=None)


@mcp.tool("get_user_story_statuses", description="Lists the available statuses for user stories within a specific project. Uses default session if session_id not provided.")
def get_user_story_statuses(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of user story statuses for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_user_story_statuses for project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(query_params={...})
        statuses = taiga_client_wrapper.api.userstory_statuses.list(query_params={"project": project_id})
        return statuses
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting user story statuses for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting user story statuses for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting user story statuses: {e}")


# --- Task Tools ---

@mcp.tool("list_tasks", description="Lists tasks within a specific project, optionally filtered. Uses default session if session_id not provided.")
def list_tasks(project_id: int, session_id: Optional[str] = None, **filters) -> List[Dict[str, Any]]:
    """Lists tasks for a project. Optional filters like 'milestone', 'status', 'user_story', 'assigned_to' can be passed as keyword arguments."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing list_tasks for project {project_id}, session {actual_session_id[:8]}, filters: {filters}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Workaround: pytaigaclient Tasks.list has a bug - passes query_params but TaigaClient.get expects params
        # Use the underlying get method directly
        parsed_filters = _parse_mcp_kwargs(filters)
        query = {"project": project_id, **parsed_filters}
        tasks = taiga_client_wrapper.api.get("/tasks", params=query)
        return tasks
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing tasks for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing tasks for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing tasks: {e}")


@mcp.tool("create_task", description="Creates a new task within a project. Uses default session if session_id not provided.")
def create_task(project_id: int, subject: str, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Creates a task. Requires project_id and subject. Optional fields (description, milestone_id, status_id, user_story_id, assigned_to_id, etc.) via kwargs."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing create_task '{subject}' in project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    if not subject:
        raise ValueError("Task subject cannot be empty.")
    try:
        # pytaigaclient Tasks.create() uses: create(project, subject, data={...})
        task = taiga_client_wrapper.api.tasks.create(project=project_id, subject=subject, data=kwargs if kwargs else None)
        logger.info(f"Task '{subject}' created successfully (ID: {task.get('id', 'N/A')}).")
        # return task.to_dict() # Remove .to_dict()
        return task # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating task '{subject}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating task '{subject}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating task: {e}")


@mcp.tool("get_task", description="Gets detailed information about a specific task by its ID. Uses default session if session_id not provided.")
def get_task(task_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves task details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_task ID {task_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Tasks expects task_id as a positional argument 
        task = taiga_client_wrapper.api.tasks.get(task_id)
        # return task.to_dict() # Remove .to_dict()
        return task # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting task {task_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting task {task_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting task: {e}")


@mcp.tool("update_task", description="Updates details of an existing task. Uses default session if session_id not provided.")
def update_task(task_id: int, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Updates a task. Pass fields to update as keyword arguments (e.g., subject, description, status_id, assigned_to)."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing update_task ID {task_id} for session {actual_session_id[:8]} with data: {kwargs}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    try:
        # Use pytaigaclient edit pattern for partial updates
        if not kwargs:
             logger.info(f"No fields provided for update on task {task_id}")
             return taiga_client_wrapper.api.tasks.get(task_id)

        # Get current task data to retrieve version
        current_task = taiga_client_wrapper.api.tasks.get(task_id)
        version = current_task.get('version')
        if not version:
            raise ValueError(f"Could not determine version for task {task_id}")
            
        # Use edit method for partial updates - pytaigaclient uses data: Dict not **kwargs
        updated_task = taiga_client_wrapper.api.tasks.edit(
            task_id=task_id,
            version=version,
            data=kwargs
        )
        logger.info(f"Task {task_id} update request sent.")
        return updated_task
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating task {task_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating task {task_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating task: {e}")


@mcp.tool("delete_task", description="Deletes a task by its ID. Uses default session if session_id not provided.")
def delete_task(task_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a task by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(
        f"Executing delete_task ID {task_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # pytaigaclient uses named args matching the parameter (e.g., task_id, not id)
        taiga_client_wrapper.api.tasks.delete(task_id=task_id)
        logger.info(f"Task {task_id} deleted successfully.")
        return {"status": "deleted", "task_id": task_id}
    except TaigaException as e:
        logger.error(
            f"Taiga API error deleting task {task_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error deleting task {task_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error deleting task: {e}")


@mcp.tool("assign_task_to_user", description="Assigns a specific task to a specific user. Uses default session if session_id not provided.")
def assign_task_to_user(task_id: int, user_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Assigns a task to a user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing assign_task_to_user: Task {task_id} -> User {user_id}, session {actual_session_id[:8]}...")
    # Delegate to update_task
    return update_task(task_id, actual_session_id, assigned_to=user_id)


@mcp.tool("unassign_task_from_user", description="Unassigns a specific task (sets assigned user to null). Uses default session if session_id not provided.")
def unassign_task_from_user(task_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Unassigns a task."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing unassign_task_from_user: Task {task_id}, session {actual_session_id[:8]}...")
    # Delegate to update_task
    return update_task(task_id, actual_session_id, assigned_to=None)


# --- Issue Tools ---

@mcp.tool("list_issues", description="Lists issues within a specific project, optionally filtered. Uses default session if session_id not provided.")
def list_issues(project_id: int, session_id: Optional[str] = None, **filters) -> List[Dict[str, Any]]:
    """Lists issues for a project. Optional filters like 'milestone', 'status', 'priority', 'severity', 'type', 'assigned_to' can be passed as kwargs."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing list_issues for project {project_id}, session {actual_session_id[:8]}, filters: {filters}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(query_params={...})
        parsed_filters = _parse_mcp_kwargs(filters)
        query = {"project": project_id, **parsed_filters}
        issues = taiga_client_wrapper.api.issues.list(query_params=query)
        return issues
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing issues for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing issues for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing issues: {e}")


@mcp.tool("create_issue", description="Creates a new issue within a project. Uses default session if session_id not provided.")
def create_issue(project_id: int, subject: str, priority_id: int, status_id: int, severity_id: int, type_id: int, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Creates an issue. Requires project_id, subject, priority_id, status_id, severity_id, type_id. Optional fields (description, assigned_to_id, etc.) via kwargs."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing create_issue '{subject}' in project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    if not subject:
        raise ValueError("Issue subject cannot be empty.")
    try:
        # pytaigaclient Issues.create() uses: create(project, subject, data={...})
        # Pack all extra fields into the data dict
        issue_data = {
            "priority": priority_id,
            "status": status_id,
            "type": type_id,
            "severity": severity_id,
            **kwargs
        }
        issue = taiga_client_wrapper.api.issues.create(
            project=project_id,
            subject=subject,
            data=issue_data
        )
        logger.info(
            f"Issue '{subject}' created successfully (ID: {issue.get('id', 'N/A')}).")
        # return issue.to_dict() # Remove .to_dict()
        return issue # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating issue '{subject}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating issue '{subject}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating issue: {e}")


@mcp.tool("get_issue", description="Gets detailed information about a specific issue by its ID. Uses default session if session_id not provided.")
def get_issue(issue_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves issue details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_issue ID {issue_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Issues expects issue_id as a positional argument
        issue = taiga_client_wrapper.api.issues.get(issue_id)
        # return issue.to_dict() # Remove .to_dict()
        return issue # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue {issue_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue {issue_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue: {e}")


@mcp.tool("update_issue", description="Updates details of an existing issue. Uses default session if session_id not provided.")
def update_issue(issue_id: int, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Updates an issue. Pass fields to update as keyword arguments (e.g., subject, description, status_id, assigned_to)."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing update_issue ID {issue_id} for session {actual_session_id[:8]} with data: {kwargs}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    try:
        # Use pytaigaclient edit pattern for partial updates
        if not kwargs:
             logger.info(f"No fields provided for update on issue {issue_id}")
             return taiga_client_wrapper.api.issues.get(issue_id)

        # Get current issue data to retrieve version
        current_issue = taiga_client_wrapper.api.issues.get(issue_id)
        version = current_issue.get('version')
        if not version:
            raise ValueError(f"Could not determine version for issue {issue_id}")
            
        # Use edit method for partial updates - pytaigaclient uses data: Dict not **kwargs
        updated_issue = taiga_client_wrapper.api.issues.edit(
            issue_id=issue_id,
            version=version,
            data=kwargs
        )
        logger.info(f"Issue {issue_id} update request sent.")
        return updated_issue
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating issue {issue_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating issue {issue_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating issue: {e}")


@mcp.tool("delete_issue", description="Deletes an issue by its ID. Uses default session if session_id not provided.")
def delete_issue(issue_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes an issue by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(
        f"Executing delete_issue ID {issue_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # pytaigaclient uses named args matching the parameter (e.g., issue_id, not id)
        taiga_client_wrapper.api.issues.delete(issue_id=issue_id)
        logger.info(f"Issue {issue_id} deleted successfully.")
        return {"status": "deleted", "issue_id": issue_id}
    except TaigaException as e:
        logger.error(
            f"Taiga API error deleting issue {issue_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error deleting issue {issue_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error deleting issue: {e}")


@mcp.tool("assign_issue_to_user", description="Assigns a specific issue to a specific user. Uses default session if session_id not provided.")
def assign_issue_to_user(issue_id: int, user_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Assigns an issue to a user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing assign_issue_to_user: Issue {issue_id} -> User {user_id}, session {actual_session_id[:8]}...")
    # Delegate to update_issue
    return update_issue(issue_id, actual_session_id, assigned_to=user_id)


@mcp.tool("unassign_issue_from_user", description="Unassigns a specific issue (sets assigned user to null). Uses default session if session_id not provided.")
def unassign_issue_from_user(issue_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Unassigns an issue."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing unassign_issue_from_user: Issue {issue_id}, session {actual_session_id[:8]}...")
    # Delegate to update_issue
    return update_issue(issue_id, actual_session_id, assigned_to=None)


@mcp.tool("get_issue_statuses", description="Lists the available statuses for issues within a specific project. Uses default session if session_id not provided.")
def get_issue_statuses(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of issue statuses for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_issue_statuses for project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(query_params={...})
        statuses = taiga_client_wrapper.api.issue_statuses.list(query_params={"project": project_id})
        return statuses
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue statuses for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue statuses for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue statuses: {e}")


@mcp.tool("get_issue_priorities", description="Lists the available priorities for issues within a specific project. Uses default session if session_id not provided.")
def get_issue_priorities(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of issue priorities for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_issue_priorities for project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(query_params={...})
        priorities = taiga_client_wrapper.api.issue_priorities.list(query_params={"project": project_id})
        return priorities
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue priorities for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue priorities for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue priorities: {e}")


@mcp.tool("get_issue_severities", description="Lists the available severities for issues within a specific project. Uses default session if session_id not provided.")
def get_issue_severities(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of issue severities for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_issue_severities for project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(query_params={...})
        severities = taiga_client_wrapper.api.issue_severities.list(query_params={"project": project_id})
        return severities
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue severities for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue severities for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue severities: {e}")


@mcp.tool("get_issue_types", description="Lists the available types for issues within a specific project. Uses default session if session_id not provided.")
def get_issue_types(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of issue types for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_issue_types for project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(query_params={...})
        types = taiga_client_wrapper.api.issue_types.list(query_params={"project": project_id})
        return types
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue types for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue types for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue types: {e}")


# --- Epic Tools ---

@mcp.tool("list_epics", description="Lists epics within a specific project, optionally filtered. Uses default session if session_id not provided.")
def list_epics(project_id: int, session_id: Optional[str] = None, **filters) -> List[Dict[str, Any]]:
    """Lists epics for a project. Optional filters like 'status', 'assigned_to' can be passed as keyword arguments."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing list_epics for project {project_id}, session {actual_session_id[:8]}, filters: {filters}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(query_params={...})
        parsed_filters = _parse_mcp_kwargs(filters)
        query = {"project": project_id, **parsed_filters}
        epics = taiga_client_wrapper.api.epics.list(query_params=query)
        return epics
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing epics for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing epics for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing epics: {e}")


@mcp.tool("create_epic", description="Creates a new epic within a project. Uses default session if session_id not provided.")
def create_epic(project_id: int, subject: str, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Creates an epic. Requires project_id and subject. Optional fields (description, status_id, assigned_to_id, color, etc.) via kwargs."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing create_epic '{subject}' in project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    if not subject:
        raise ValueError("Epic subject cannot be empty.")
    try:
        # Use pytaigaclient syntax: client.resource.create(project=..., subject=..., **kwargs)
        epic = taiga_client_wrapper.api.epics.create(project=project_id, subject=subject, **kwargs)
        logger.info(f"Epic '{subject}' created successfully (ID: {epic.get('id', 'N/A')}).")
        # return epic.to_dict() # Remove .to_dict()
        return epic # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating epic '{subject}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating epic '{subject}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating epic: {e}")


@mcp.tool("get_epic", description="Gets detailed information about a specific epic by its ID. Uses default session if session_id not provided.")
def get_epic(epic_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves epic details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_epic ID {epic_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Epics expects epic_id as a positional argument
        epic = taiga_client_wrapper.api.epics.get(epic_id)
        # return epic.to_dict() # Remove .to_dict()
        return epic # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting epic {epic_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting epic {epic_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting epic: {e}")


@mcp.tool("update_epic", description="Updates details of an existing epic. Uses default session if session_id not provided.")
def update_epic(epic_id: int, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Updates an epic. Pass fields to update as keyword arguments (e.g., subject, description, status_id, assigned_to, color)."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing update_epic ID {epic_id} for session {actual_session_id[:8]} with data: {kwargs}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    try:
        # Use pytaigaclient edit pattern for partial updates
        if not kwargs:
             logger.info(f"No fields provided for update on epic {epic_id}")
             return taiga_client_wrapper.api.epics.get(epic_id)

        # Get current epic data to retrieve version
        current_epic = taiga_client_wrapper.api.epics.get(epic_id)
        version = current_epic.get('version')
        if not version:
            raise ValueError(f"Could not determine version for epic {epic_id}")
            
        # Use edit method for partial updates with keyword arguments
        updated_epic = taiga_client_wrapper.api.epics.edit(
            epic_id=epic_id,
            version=version,
            **kwargs
        )
        logger.info(f"Epic {epic_id} update request sent.")
        return updated_epic
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating epic {epic_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating epic {epic_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating epic: {e}")


@mcp.tool("delete_epic", description="Deletes an epic by its ID. Uses default session if session_id not provided.")
def delete_epic(epic_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes an epic by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(
        f"Executing delete_epic ID {epic_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # pytaigaclient uses named args matching the parameter (e.g., epic_id, not id)
        taiga_client_wrapper.api.epics.delete(epic_id=epic_id)
        logger.info(f"Epic {epic_id} deleted successfully.")
        return {"status": "deleted", "epic_id": epic_id}
    except TaigaException as e:
        logger.error(
            f"Taiga API error deleting epic {epic_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error deleting epic {epic_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error deleting epic: {e}")


@mcp.tool("assign_epic_to_user", description="Assigns a specific epic to a specific user. Uses default session if session_id not provided.")
def assign_epic_to_user(epic_id: int, user_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Assigns an epic to a user."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing assign_epic_to_user: Epic {epic_id} -> User {user_id}, session {actual_session_id[:8]}...")
    # Delegate to update_epic
    return update_epic(epic_id, actual_session_id, assigned_to=user_id)


@mcp.tool("unassign_epic_from_user", description="Unassigns a specific epic (sets assigned user to null). Uses default session if session_id not provided.")
def unassign_epic_from_user(epic_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Unassigns an epic."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing unassign_epic_from_user: Epic {epic_id}, session {actual_session_id[:8]}...")
    # Delegate to update_epic
    return update_epic(epic_id, actual_session_id, assigned_to=None)


# --- Milestone (Sprint) Tools ---

@mcp.tool("list_milestones", description="Lists milestones (sprints) within a specific project. Uses default session if session_id not provided.")
def list_milestones(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists milestones for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing list_milestones for project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: milestones.list(project=...) - keyword arg
        milestones = taiga_client_wrapper.api.milestones.list(project=project_id)
        return milestones
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing milestones for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing milestones for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing milestones: {e}")


@mcp.tool("create_milestone", description="Creates a new milestone (sprint) within a project. Uses default session if session_id not provided.")
def create_milestone(project_id: int, name: str, estimated_start: str, estimated_finish: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Creates a milestone. Requires project_id, name, estimated_start (YYYY-MM-DD), and estimated_finish (YYYY-MM-DD)."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing create_milestone '{name}' in project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not all([name, estimated_start, estimated_finish]):
        raise ValueError(
            "Milestone requires name, estimated_start, and estimated_finish.")
    try:
        # Use pytaigaclient syntax: client.resource.create(...)
        milestone = taiga_client_wrapper.api.milestones.create(
            project=project_id,             # Changed project_id to project
            name=name,
            estimated_start=estimated_start,
            estimated_finish=estimated_finish
        )
        logger.info(
            f"Milestone '{name}' created successfully (ID: {milestone.get('id', 'N/A')}).")
        # return milestone.to_dict() # Remove .to_dict()
        return milestone # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating milestone '{name}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating milestone '{name}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating milestone: {e}")


@mcp.tool("get_milestone", description="Gets detailed information about a specific milestone by its ID. Uses default session if session_id not provided.")
def get_milestone(milestone_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves milestone details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_milestone ID {milestone_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Milestones expects milestone_id as a positional argument
        milestone = taiga_client_wrapper.api.milestones.get(milestone_id)
        # return milestone.to_dict() # Remove .to_dict()
        return milestone # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting milestone {milestone_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting milestone {milestone_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting milestone: {e}")


@mcp.tool("update_milestone", description="Updates details of an existing milestone. Uses default session if session_id not provided.")
def update_milestone(milestone_id: int, session_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """Updates a milestone. Pass fields to update as kwargs (e.g., name, estimated_start, estimated_finish)."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing update_milestone ID {milestone_id} for session {actual_session_id[:8]} with data: {kwargs}")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    # Parse kwargs in case they come as a JSON string from MCP
    kwargs = _parse_mcp_kwargs(kwargs)
    try:
        # Use pytaigaclient edit pattern for partial updates
        if not kwargs:
             logger.info(f"No fields provided for update on milestone {milestone_id}")
             return taiga_client_wrapper.api.milestones.get(milestone_id)

        # Get current milestone data to retrieve version
        current_milestone = taiga_client_wrapper.api.milestones.get(milestone_id)
        version = current_milestone.get('version')
        if not version:
            raise ValueError(f"Could not determine version for milestone {milestone_id}")
            
        # Use edit method for partial updates with keyword arguments
        updated_milestone = taiga_client_wrapper.api.milestones.edit(
            milestone_id=milestone_id,
            version=version,
            **kwargs
        )
        logger.info(f"Milestone {milestone_id} update request sent.")
        return updated_milestone
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating milestone {milestone_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating milestone {milestone_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating milestone: {e}")


@mcp.tool("delete_milestone", description="Deletes a milestone by its ID. Uses default session if session_id not provided.")
def delete_milestone(milestone_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Deletes a milestone by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.warning(
        f"Executing delete_milestone ID {milestone_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # pytaigaclient uses named args matching the parameter (e.g., milestone_id, not id)
        taiga_client_wrapper.api.milestones.delete(milestone_id=milestone_id)
        logger.info(f"Milestone {milestone_id} deleted successfully.")
        return {"status": "deleted", "milestone_id": milestone_id}
    except TaigaException as e:
        logger.error(
            f"Taiga API error deleting milestone {milestone_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error deleting milestone {milestone_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error deleting milestone: {e}")


# --- User Management Tools ---

@mcp.tool("get_project_members", description="Lists members of a specific project. Uses default session if session_id not provided.")
def get_project_members(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves the list of members for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_project_members for project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(query_params={...})
        members = taiga_client_wrapper.api.memberships.list(query_params={"project": project_id})
        return members
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting members for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting members for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting project members: {e}")


@mcp.tool("invite_project_user", description="Invites a user to a project by email with a specific role. Uses default session if session_id not provided.")
def invite_project_user(project_id: int, email: str, role_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Invites a user via email to join the project with the specified role ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing invite_project_user {email} to project {project_id} (role {role_id}), session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    if not email:
        raise ValueError("Email cannot be empty.")
    try:
        # Use pytaigaclient memberships resource invite method
        # Check pytaigaclient signature for param names (project, email, role_id)
        invitation_result = taiga_client_wrapper.api.memberships.invite(
            project=project_id, email=email, role_id=role_id # Changed project_id to project
        )
        logger.info(f"Invitation request sent to {email} for project {project_id}.")
        # Return the result from the invite call (might be dict or status)
        return invitation_result if isinstance(invitation_result, dict) else {"status": "invited", "email": email, "details": invitation_result}
    except TaigaException as e:
        logger.error(
            f"Taiga API error inviting user {email} to project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error inviting user {email} to project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error inviting user: {e}")


# --- Wiki Tools ---

@mcp.tool("list_wiki_pages", description="Lists wiki pages within a specific project. Uses default session if session_id not provided.")
def list_wiki_pages(project_id: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists wiki pages for a project."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing list_wiki_pages for project {project_id}, session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Use pytaigaclient syntax: client.resource.list(query_params={...})
        pages = taiga_client_wrapper.api.wiki.list(query_params={"project": project_id})
        return pages
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing wiki pages for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing wiki pages for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing wiki pages: {e}")


@mcp.tool("get_wiki_page", description="Gets a specific wiki page by its ID. Uses default session if session_id not provided.")
def get_wiki_page(wiki_page_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves wiki page details by ID."""
    actual_session_id = _get_session_id(session_id)
    logger.info(
        f"Executing get_wiki_page ID {wiki_page_id} for session {actual_session_id[:8]}...")
    taiga_client_wrapper = _get_authenticated_client(actual_session_id)
    try:
        # Wiki expects wiki_page_id as a positional argument
        page = taiga_client_wrapper.api.wiki.get(wiki_page_id)
        # return page.to_dict() # Remove .to_dict()
        return page # Return directly
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting wiki page {wiki_page_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting wiki page {wiki_page_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting wiki page: {e}")


# --- Session Management Tools ---

@mcp.tool("logout", description="Invalidates the current session_id. Uses default session if session_id not provided.")
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
        logger.warning(
            f"Attempted to log out non-existent session: {actual_session_id[:8]}")
        return {"status": "session_not_found", "session_id": actual_session_id}


@mcp.tool("session_status", description="Checks if the provided session_id is currently active and valid. Uses default session if session_id not provided.")
def session_status(session_id: Optional[str] = None) -> Dict[str, Any]:
    """Checks the validity of the current session_id."""
    actual_session_id = _get_session_id(session_id)
    logger.debug(
        f"Executing session_status check for session {actual_session_id[:8]}...")
    client_wrapper = active_sessions.get(actual_session_id)
    if client_wrapper and client_wrapper.is_authenticated:
        try:
            # Use pytaigaclient users.get_me() call
            me = client_wrapper.api.users.get_me()
            # Extract username from the returned dict
            username = me.get('username', 'Unknown')
            logger.debug(
                f"Session {actual_session_id[:8]} is active for user {username}.")
            return {"status": "active", "session_id": actual_session_id, "username": username}
        except TaigaException:
            logger.warning(
                f"Session {actual_session_id[:8]} found but token seems invalid (API check failed).")
            # Clean up invalid session
            active_sessions.pop(actual_session_id, None)
            return {"status": "inactive", "reason": "token_invalid", "session_id": actual_session_id}
        except Exception as e: # Catch broader exceptions during the 'me' call
             logger.error(f"Unexpected error during session status check for {actual_session_id[:8]}: {e}", exc_info=True)
             # Return a distinct status for unexpected errors during check
             return {"status": "error", "reason": "check_failed", "session_id": actual_session_id}
    elif client_wrapper: # Client exists but not authenticated (shouldn't happen with current login logic)
        logger.warning(
            f"Session {actual_session_id[:8]} exists but client wrapper is not authenticated.")
        return {"status": "inactive", "reason": "not_authenticated", "session_id": actual_session_id}
    else: # Session ID not found
        logger.debug(f"Session {actual_session_id[:8]} not found.")
        return {"status": "inactive", "reason": "not_found", "session_id": actual_session_id}


# --- Run the server ---
if __name__ == "__main__":
    mcp.run()
