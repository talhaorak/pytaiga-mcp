# server_fastmcp.py
import logging
import logging.config
import uuid
from typing import Optional, List, Dict, Any

from mcp.server.fastmcp import FastMCP
from taiga.exceptions import TaigaException

# Assuming taiga_client.py is in the same directory or accessible via PYTHONPATH
from src.taiga_client import TaigaClientWrapper

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Log to stderr by default
    ]
)
logger = logging.getLogger(__name__)
# Quiet down taiga library logging
logging.getLogger("taiga").setLevel(logging.WARNING)

# --- Manual Session Management ---
# Store active sessions: session_id -> TaigaClientWrapper instance
active_sessions: Dict[str, TaigaClientWrapper] = {}

# --- MCP Server Definition ---
# No lifespan needed for this approach
mcp = FastMCP(
    "Taiga Bridge (Session ID)",
    dependencies=["python-taiga"]
)

# --- Helper Function for Session Validation ---


def _get_authenticated_client(session_id: str) -> TaigaClientWrapper:
    """
    Retrieves the authenticated TaigaClientWrapper for a given session ID.
    Raises PermissionError if the session is invalid or not found.
    """
    client = active_sessions.get(session_id)
    # Also check if the client object itself exists and is authenticated
    if not client or not client.is_authenticated:
        logger.warning(f"Invalid or expired session ID provided: {session_id}")
        # Raise PermissionError - FastMCP will map this to an appropriate error response
        raise PermissionError(
            f"Invalid or expired session ID: '{session_id}'. Please login again.")
    logger.debug(f"Retrieved valid client for session ID: {session_id}")
    return client

# --- MCP Tools ---


@mcp.tool("login", description="Logs into a Taiga instance using username/password and returns a session_id for subsequent authenticated calls.")
def login(host: str, username: str, password: str) -> Dict[str, str]:
    """
    Handles Taiga login and creates a session.

    Args:
        host: The URL of the Taiga instance (e.g., 'https://tree.taiga.io').
        username: The Taiga username.
        password: The Taiga password.

    Returns:
        A dictionary containing the session_id upon successful login.
        Example: {"session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}
    """
    logger.info(f"Executing login tool for user '{username}' on host '{host}'")

    try:
        wrapper = TaigaClientWrapper(host=host)
        login_successful = wrapper.login(username=username, password=password)

        if login_successful:
            # Generate a unique session ID
            new_session_id = str(uuid.uuid4())
            # Store the authenticated wrapper in our manual session store
            active_sessions[new_session_id] = wrapper
            logger.info(
                f"Login successful for '{username}'. Created session ID: {new_session_id}")
            # Return the session ID to the client
            return {"session_id": new_session_id}
        else:
            # Should not happen if login raises exception on failure, but handle defensively
            logger.error(
                f"Login attempt for '{username}' returned False unexpectedly.")
            raise RuntimeError("Login failed for an unknown reason.")

    except (ValueError, TaigaException) as e:
        logger.error(f"Login failed for '{username}': {e}", exc_info=False)
        # Re-raise the exception - FastMCP will turn it into an error response
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error during login for '{username}': {e}", exc_info=True)
        raise RuntimeError(
            f"An unexpected server error occurred during login: {e}")

# server_fastmcp.py

# ... (keep existing imports, logging setup, active_sessions, FastMCP instance) ...
# ... (keep _get_authenticated_client helper function) ...
# ... (keep login tool function) ...


# --- Project Tools ---

@mcp.tool("list_projects", description="Lists projects accessible to the user associated with the provided session_id.")
def list_projects(session_id: str) -> List[Dict[str, Any]]:
    """Lists projects accessible by the authenticated user."""
    logger.info(f"Executing list_projects for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        projects = taiga_client.api.projects.list()
        result = [p.to_dict() for p in projects]
        logger.info(
            f"list_projects successful for session {session_id[:8]}, found {len(result)} projects.")
        return result
    except TaigaException as e:
        logger.error(f"Taiga API error listing projects: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(f"Unexpected error listing projects: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing projects: {e}")


@mcp.tool("list_all_projects", description="Lists all projects visible to the user (requires admin privileges for full list). Uses the provided session_id.")
def list_all_projects(session_id: str) -> List[Dict[str, Any]]:
    """Lists all projects visible to the authenticated user (scope depends on permissions)."""
    logger.info(f"Executing list_all_projects for session {session_id[:8]}...")
    # Note: python-taiga's list() shows what the user *can* see.
    # True "all" requires admin user login.
    # Functionally identical for the library call
    return list_projects(session_id)


@mcp.tool("get_project", description="Gets detailed information about a specific project by its ID.")
def get_project(session_id: str, project_id: int) -> Dict[str, Any]:
    """Retrieves project details by ID."""
    logger.info(
        f"Executing get_project ID {project_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Correct: Use the manager's get method for ID lookup
        project = taiga_client.api.projects.get(project_id)
        return project.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting project: {e}")


@mcp.tool("get_project_by_slug", description="Gets detailed information about a specific project by its slug.")
def get_project_by_slug(session_id: str, slug: str) -> Dict[str, Any]:
    """Retrieves project details by slug."""
    logger.info(
        f"Executing get_project_by_slug '{slug}' for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Correct: Use the specific get_by_slug method from the Projects manager
        project = taiga_client.api.projects.get_by_slug(slug=slug)
        return project.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting project by slug '{slug}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting project by slug '{slug}': {e}", exc_info=True)
        raise RuntimeError(f"Server error getting project by slug: {e}")


@mcp.tool("update_project", description="Updates details of an existing project.")
def update_project(session_id: str, project_id: int, **kwargs) -> Dict[str, Any]:
    """Updates a project. Pass fields to update as keyword arguments (e.g., name='New Name', description='New Desc')."""
    logger.info(
        f"Executing update_project ID {project_id} for session {session_id[:8]} with data: {kwargs}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        project = taiga_client.api.projects.get(project_id)
        # Apply updates - only update allowed fields if possible/needed
        allowed_updates = taiga_client.api.projects.instance.allowed_params
        updated = False
        for key, value in kwargs.items():
            if key in allowed_updates and hasattr(project, key):
                setattr(project, key, value)
                updated = True
            else:
                logger.warning(
                    f"Skipping non-updatable/unknown field '{key}' for project {project_id}")

        if updated:
            project.update()  # Use the instance update method
            logger.info(f"Project {project_id} updated successfully.")
        else:
            logger.info(
                f"No valid fields provided for update on project {project_id}")

        return project.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating project: {e}")


@mcp.tool("delete_project", description="Deletes a project by its ID. This is irreversible.")
def delete_project(session_id: str, project_id: int) -> Dict[str, Any]:
    """Deletes a project by ID."""
    logger.warning(
        f"Executing delete_project ID {project_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        taiga_client.api.projects.delete(project_id)
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


@mcp.tool("get_project_roles", description="Lists the available roles within a specific project.")
def get_project_roles(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the list of roles for a project."""
    logger.info(
        f"Executing get_project_roles for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        roles = taiga_client.api.roles.list(project=project_id)
        return [r.to_dict() for r in roles]
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting roles for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting roles for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting roles: {e}")


# --- User Story Tools ---

@mcp.tool("list_user_stories", description="Lists user stories within a specific project, optionally filtered.")
def list_user_stories(session_id: str, project_id: int, **filters) -> List[Dict[str, Any]]:
    """Lists user stories for a project. Optional filters like 'milestone', 'status', 'assigned_to' can be passed as keyword arguments."""
    logger.info(
        f"Executing list_user_stories for project {project_id}, session {session_id[:8]}, filters: {filters}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        stories = taiga_client.api.user_stories.list(
            project=project_id, **filters)
        return [s.to_dict() for s in stories]
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing user stories for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing user stories for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing user stories: {e}")


@mcp.tool("create_user_story", description="Creates a new user story within a project.")
def create_user_story(session_id: str, project_id: int, subject: str, **kwargs) -> Dict[str, Any]:
    """Creates a user story. Requires project_id and subject. Optional fields (description, milestone_id, status_id, assigned_to_id, etc.) via kwargs."""
    logger.info(
        f"Executing create_user_story '{subject}' in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    if not subject:
        raise ValueError("User story subject cannot be empty.")
    try:
        story = taiga_client.api.user_stories.create(
            project_id, subject, **kwargs)
        logger.info(
            f"User story '{subject}' created successfully (ID: {story.id}).")
        return story.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating user story '{subject}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating user story '{subject}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating user story: {e}")


@mcp.tool("get_user_story", description="Gets detailed information about a specific user story by its ID.")
def get_user_story(session_id: str, user_story_id: int) -> Dict[str, Any]:
    """Retrieves user story details by ID."""
    logger.info(
        f"Executing get_user_story ID {user_story_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        story = taiga_client.api.user_stories.get(user_story_id)
        return story.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting user story {user_story_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting user story {user_story_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting user story: {e}")


@mcp.tool("get_user_story_by_ref", description="Gets detailed information about a specific user story by its reference number within a project.")
def get_user_story_by_ref(session_id: str, project_id: int, ref: int) -> Dict[str, Any]:
    """Retrieves user story details by project ID and reference number."""
    logger.info(
        f"Executing get_user_story_by_ref Ref {ref} in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Correct: Get the project object first, then call its helper method
        project = taiga_client.api.projects.get(project_id)
        story = project.get_userstory_by_ref(ref=ref)  # Use Project's method
        if story is None:
            raise TaigaException(
                f"User Story with ref {ref} not found in project {project_id}")
        return story.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting user story ref {ref} (project {project_id}): {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting user story ref {ref} (project {project_id}): {e}", exc_info=True)
        raise RuntimeError(f"Server error getting user story by ref: {e}")


@mcp.tool("update_user_story", description="Updates details of an existing user story.")
def update_user_story(session_id: str, user_story_id: int, **kwargs) -> Dict[str, Any]:
    """Updates a user story. Pass fields to update as keyword arguments (e.g., subject, description, status_id, assigned_to)."""
    logger.info(
        f"Executing update_user_story ID {user_story_id} for session {session_id[:8]} with data: {kwargs}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        story = taiga_client.api.user_stories.get(user_story_id)
        allowed_updates = taiga_client.api.user_stories.instance.allowed_params
        updated = False
        for key, value in kwargs.items():
            # Special handling for assigned_to=None to unassign
            if key == "assigned_to" and value is None:
                setattr(story, key, None)
                updated = True
            elif key in allowed_updates and hasattr(story, key):
                setattr(story, key, value)
                updated = True
            else:
                logger.warning(
                    f"Skipping non-updatable/unknown field '{key}' for user story {user_story_id}")

        if updated:
            story.update()
            logger.info(f"User story {user_story_id} updated successfully.")
        else:
            logger.info(
                f"No valid fields provided for update on user story {user_story_id}")

        return story.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating user story {user_story_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating user story {user_story_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating user story: {e}")


@mcp.tool("delete_user_story", description="Deletes a user story by its ID.")
def delete_user_story(session_id: str, user_story_id: int) -> Dict[str, Any]:
    """Deletes a user story by ID."""
    logger.warning(
        f"Executing delete_user_story ID {user_story_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        taiga_client.api.user_stories.delete(user_story_id)
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


@mcp.tool("assign_user_story_to_user", description="Assigns a specific user story to a specific user.")
def assign_user_story_to_user(session_id: str, user_story_id: int, user_id: int) -> Dict[str, Any]:
    """Assigns a user story to a user."""
    logger.info(
        f"Executing assign_user_story_to_user: US {user_story_id} -> User {user_id}, session {session_id[:8]}...")
    # Update the user story with the new assigned_to id
    return update_user_story(session_id, user_story_id, assigned_to=user_id)


@mcp.tool("unassign_user_story_from_user", description="Unassigns a specific user story (sets assigned user to null).")
def unassign_user_story_from_user(session_id: str, user_story_id: int) -> Dict[str, Any]:
    """Unassigns a user story."""
    logger.info(
        f"Executing unassign_user_story_from_user: US {user_story_id}, session {session_id[:8]}...")
    # Update the user story setting assigned_to to None (or appropriate value for unassign)
    return update_user_story(session_id, user_story_id, assigned_to=None)


@mcp.tool("get_user_story_statuses", description="Lists the available statuses for user stories within a specific project.")
def get_user_story_statuses(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the list of user story statuses for a project."""
    logger.info(
        f"Executing get_user_story_statuses for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        statuses = taiga_client.api.user_story_statuses.list(
            project=project_id)
        return [s.to_dict() for s in statuses]
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting user story statuses for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting user story statuses for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting user story statuses: {e}")


# --- Task Tools ---

@mcp.tool("list_tasks", description="Lists tasks within a specific project, optionally filtered.")
def list_tasks(session_id: str, project_id: int, **filters) -> List[Dict[str, Any]]:
    """Lists tasks for a project. Optional filters like 'milestone', 'status', 'user_story', 'assigned_to' can be passed as keyword arguments."""
    logger.info(
        f"Executing list_tasks for project {project_id}, session {session_id[:8]}, filters: {filters}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        tasks = taiga_client.api.tasks.list(project=project_id, **filters)
        return [t.to_dict() for t in tasks]
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing tasks for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing tasks for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing tasks: {e}")


@mcp.tool("create_task", description="Creates a new task within a project.")
def create_task(session_id: str, project_id: int, subject: str, **kwargs) -> Dict[str, Any]:
    """Creates a task. Requires project_id and subject. Optional fields (description, milestone_id, status_id, user_story_id, assigned_to_id, etc.) via kwargs."""
    logger.info(
        f"Executing create_task '{subject}' in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    if not subject:
        raise ValueError("Task subject cannot be empty.")
    try:
        task = taiga_client.api.tasks.create(project_id, subject, **kwargs)
        logger.info(f"Task '{subject}' created successfully (ID: {task.id}).")
        return task.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating task '{subject}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating task '{subject}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating task: {e}")


@mcp.tool("get_task", description="Gets detailed information about a specific task by its ID.")
def get_task(session_id: str, task_id: int) -> Dict[str, Any]:
    """Retrieves task details by ID."""
    logger.info(
        f"Executing get_task ID {task_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        task = taiga_client.api.tasks.get(task_id)
        return task.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting task {task_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting task {task_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting task: {e}")


@mcp.tool("get_task_by_ref", description="Gets detailed information about a specific task by its reference number within a project.")
def get_task_by_ref(session_id: str, project_id: int, ref: int) -> Dict[str, Any]:
    """Retrieves task details by project ID and reference number."""
    logger.info(
        f"Executing get_task_by_ref Ref {ref} in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Correct: Get the project object first, then call its helper method
        project = taiga_client.api.projects.get(project_id)
        task = project.get_task_by_ref(ref=ref)  # Use Project's method
        if task is None:
            raise TaigaException(
                f"Task with ref {ref} not found in project {project_id}")
        return task.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting task ref {ref} (project {project_id}): {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting task ref {ref} (project {project_id}): {e}", exc_info=True)
        raise RuntimeError(f"Server error getting task by ref: {e}")


@mcp.tool("update_task", description="Updates details of an existing task.")
def update_task(session_id: str, task_id: int, **kwargs) -> Dict[str, Any]:
    """Updates a task. Pass fields to update as keyword arguments (e.g., subject, description, status_id, assigned_to)."""
    logger.info(
        f"Executing update_task ID {task_id} for session {session_id[:8]} with data: {kwargs}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        task = taiga_client.api.tasks.get(task_id)
        allowed_updates = taiga_client.api.tasks.instance.allowed_params
        updated = False
        for key, value in kwargs.items():
            if key == "assigned_to" and value is None:
                setattr(task, key, None)
                updated = True
            elif key in allowed_updates and hasattr(task, key):
                setattr(task, key, value)
                updated = True
            else:
                logger.warning(
                    f"Skipping non-updatable/unknown field '{key}' for task {task_id}")

        if updated:
            task.update()
            logger.info(f"Task {task_id} updated successfully.")
        else:
            logger.info(
                f"No valid fields provided for update on task {task_id}")

        return task.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating task {task_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating task {task_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating task: {e}")


@mcp.tool("delete_task", description="Deletes a task by its ID.")
def delete_task(session_id: str, task_id: int) -> Dict[str, Any]:
    """Deletes a task by ID."""
    logger.warning(
        f"Executing delete_task ID {task_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        taiga_client.api.tasks.delete(task_id)
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


@mcp.tool("assign_task_to_user", description="Assigns a specific task to a specific user.")
def assign_task_to_user(session_id: str, task_id: int, user_id: int) -> Dict[str, Any]:
    """Assigns a task to a user."""
    logger.info(
        f"Executing assign_task_to_user: Task {task_id} -> User {user_id}, session {session_id[:8]}...")
    return update_task(session_id, task_id, assigned_to=user_id)


@mcp.tool("unassign_task_from_user", description="Unassigns a specific task (sets assigned user to null).")
def unassign_task_from_user(session_id: str, task_id: int) -> Dict[str, Any]:
    """Unassigns a task."""
    logger.info(
        f"Executing unassign_task_from_user: Task {task_id}, session {session_id[:8]}...")
    return update_task(session_id, task_id, assigned_to=None)


@mcp.tool("get_task_statuses", description="Lists the available statuses for tasks within a specific project.")
def get_task_statuses(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the list of task statuses for a project."""
    logger.info(
        f"Executing get_task_statuses for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        statuses = taiga_client.api.task_statuses.list(project=project_id)
        return [s.to_dict() for s in statuses]
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting task statuses for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting task statuses for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting task statuses: {e}")


# --- Issue Tools ---

@mcp.tool("list_issues", description="Lists issues within a specific project, optionally filtered.")
def list_issues(session_id: str, project_id: int, **filters) -> List[Dict[str, Any]]:
    """Lists issues for a project. Optional filters like 'milestone', 'status', 'priority', 'severity', 'type', 'assigned_to' can be passed as kwargs."""
    logger.info(
        f"Executing list_issues for project {project_id}, session {session_id[:8]}, filters: {filters}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        issues = taiga_client.api.issues.list(project=project_id, **filters)
        return [i.to_dict() for i in issues]
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing issues for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing issues for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing issues: {e}")


@mcp.tool("create_issue", description="Creates a new issue within a project.")
def create_issue(session_id: str, project_id: int, subject: str, priority_id: int, status_id: int, severity_id: int, type_id: int, **kwargs) -> Dict[str, Any]:
    """Creates an issue. Requires project_id, subject, priority_id, status_id, severity_id, type_id. Optional fields (description, assigned_to_id, etc.) via kwargs."""
    logger.info(
        f"Executing create_issue '{subject}' in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    if not subject:
        raise ValueError("Issue subject cannot be empty.")
    try:
        # Correct: Use keyword arguments matching the model's create signature
        issue = taiga_client.api.issues.create(
            project=project_id,
            subject=subject,
            priority=priority_id,  # Use model param name 'priority'
            status=status_id,      # Use model param name 'status'
            issue_type=type_id,    # Use model param name 'issue_type'
            severity=severity_id,  # Use model param name 'severity'
            **kwargs
        )
        logger.info(
            f"Issue '{subject}' created successfully (ID: {issue.id}).")
        return issue.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating issue '{subject}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating issue '{subject}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating issue: {e}")


@mcp.tool("get_issue", description="Gets detailed information about a specific issue by its ID.")
def get_issue(session_id: str, issue_id: int) -> Dict[str, Any]:
    """Retrieves issue details by ID."""
    logger.info(
        f"Executing get_issue ID {issue_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        issue = taiga_client.api.issues.get(issue_id)
        return issue.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue {issue_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue {issue_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue: {e}")


@mcp.tool("get_issue_by_ref", description="Gets detailed information about a specific issue by its reference number within a project.")
def get_issue_by_ref(session_id: str, project_id: int, ref: int) -> Dict[str, Any]:
    """Retrieves issue details by project ID and reference number."""
    logger.info(
        f"Executing get_issue_by_ref Ref {ref} in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Correct: Get the project object first, then call its helper method
        project = taiga_client.api.projects.get(project_id)
        issue = project.get_issue_by_ref(ref=ref)  # Use Project's method
        if issue is None:
            raise TaigaException(
                f"Issue with ref {ref} not found in project {project_id}")
        return issue.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue ref {ref} (project {project_id}): {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue ref {ref} (project {project_id}): {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue by ref: {e}")


@mcp.tool("update_issue", description="Updates details of an existing issue.")
def update_issue(session_id: str, issue_id: int, **kwargs) -> Dict[str, Any]:
    """Updates an issue. Pass fields to update as keyword arguments (e.g., subject, description, status_id, assigned_to)."""
    logger.info(
        f"Executing update_issue ID {issue_id} for session {session_id[:8]} with data: {kwargs}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        issue = taiga_client.api.issues.get(issue_id)
        allowed_updates = taiga_client.api.issues.instance.allowed_params
        updated = False

        # Rename incoming 'type_id' if necessary to match model 'type' attribute
        if 'type_id' in kwargs and 'type' not in kwargs:
            kwargs['type'] = kwargs.pop('type_id')
        if 'priority_id' in kwargs and 'priority' not in kwargs:
            kwargs['priority'] = kwargs.pop('priority_id')
        if 'severity_id' in kwargs and 'severity' not in kwargs:
            kwargs['severity'] = kwargs.pop('severity_id')
        if 'status_id' in kwargs and 'status' not in kwargs:
            kwargs['status'] = kwargs.pop('status_id')

        for key, value in kwargs.items():
            if key == "assigned_to" and value is None:
                setattr(issue, key, None)
                updated = True
            # Check against allowed_params from Issue model
            elif key in allowed_updates and hasattr(issue, key):
                setattr(issue, key, value)
                updated = True
            else:
                logger.warning(
                    f"Skipping non-updatable/unknown field '{key}' for issue {issue_id}")

        if updated:
            issue.update()
            logger.info(f"Issue {issue_id} updated successfully.")
        else:
            logger.info(
                f"No valid fields provided for update on issue {issue_id}")

        return issue.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating issue {issue_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating issue {issue_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating issue: {e}")


@mcp.tool("delete_issue", description="Deletes an issue by its ID.")
def delete_issue(session_id: str, issue_id: int) -> Dict[str, Any]:
    """Deletes an issue by ID."""
    logger.warning(
        f"Executing delete_issue ID {issue_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        taiga_client.api.issues.delete(issue_id)
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


@mcp.tool("assign_issue_to_user", description="Assigns a specific issue to a specific user.")
def assign_issue_to_user(session_id: str, issue_id: int, user_id: int) -> Dict[str, Any]:
    """Assigns an issue to a user."""
    logger.info(
        f"Executing assign_issue_to_user: Issue {issue_id} -> User {user_id}, session {session_id[:8]}...")
    return update_issue(session_id, issue_id, assigned_to=user_id)


@mcp.tool("unassign_issue_from_user", description="Unassigns a specific issue (sets assigned user to null).")
def unassign_issue_from_user(session_id: str, issue_id: int) -> Dict[str, Any]:
    """Unassigns an issue."""
    logger.info(
        f"Executing unassign_issue_from_user: Issue {issue_id}, session {session_id[:8]}...")
    return update_issue(session_id, issue_id, assigned_to=None)


@mcp.tool("get_issue_statuses", description="Lists the available statuses for issues within a specific project.")
def get_issue_statuses(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the list of issue statuses for a project."""
    logger.info(
        f"Executing get_issue_statuses for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        statuses = taiga_client.api.issue_statuses.list(project=project_id)
        return [s.to_dict() for s in statuses]
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue statuses for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue statuses for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue statuses: {e}")


@mcp.tool("get_issue_priorities", description="Lists the available priorities for issues within a specific project.")
def get_issue_priorities(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the list of issue priorities for a project."""
    logger.info(
        f"Executing get_issue_priorities for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        priorities = taiga_client.api.priorities.list(project=project_id)
        return [p.to_dict() for p in priorities]
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue priorities for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue priorities for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue priorities: {e}")


@mcp.tool("get_issue_severities", description="Lists the available severities for issues within a specific project.")
def get_issue_severities(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the list of issue severities for a project."""
    logger.info(
        f"Executing get_issue_severities for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        severities = taiga_client.api.severities.list(project=project_id)
        return [s.to_dict() for s in severities]
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue severities for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue severities for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue severities: {e}")


@mcp.tool("get_issue_types", description="Lists the available types for issues within a specific project.")
def get_issue_types(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the list of issue types for a project."""
    logger.info(
        f"Executing get_issue_types for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        types = taiga_client.api.issue_types.list(project=project_id)
        return [t.to_dict() for t in types]
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting issue types for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting issue types for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting issue types: {e}")


# --- Epic Tools ---

@mcp.tool("list_epics", description="Lists epics within a specific project, optionally filtered.")
def list_epics(session_id: str, project_id: int, **filters) -> List[Dict[str, Any]]:
    """Lists epics for a project. Optional filters like 'status', 'assigned_to' can be passed as keyword arguments."""
    logger.info(
        f"Executing list_epics for project {project_id}, session {session_id[:8]}, filters: {filters}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        epics = taiga_client.api.epics.list(project=project_id, **filters)
        return [e.to_dict() for e in epics]
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing epics for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing epics for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing epics: {e}")


@mcp.tool("create_epic", description="Creates a new epic within a project.")
def create_epic(session_id: str, project_id: int, subject: str, **kwargs) -> Dict[str, Any]:
    """Creates an epic. Requires project_id and subject. Optional fields (description, status_id, assigned_to_id, color, etc.) via kwargs."""
    logger.info(
        f"Executing create_epic '{subject}' in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    if not subject:
        raise ValueError("Epic subject cannot be empty.")
    try:
        epic = taiga_client.api.epics.create(project_id, subject, **kwargs)
        logger.info(f"Epic '{subject}' created successfully (ID: {epic.id}).")
        return epic.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating epic '{subject}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating epic '{subject}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating epic: {e}")


@mcp.tool("get_epic", description="Gets detailed information about a specific epic by its ID.")
def get_epic(session_id: str, epic_id: int) -> Dict[str, Any]:
    """Retrieves epic details by ID."""
    logger.info(
        f"Executing get_epic ID {epic_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        epic = taiga_client.api.epics.get(epic_id)
        return epic.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting epic {epic_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting epic {epic_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting epic: {e}")


@mcp.tool("get_epic_by_ref", description="Gets detailed information about a specific epic by its reference number within a project.")
def get_epic_by_ref(session_id: str, project_id: int, ref: int) -> Dict[str, Any]:
    """Retrieves epic details by project ID and reference number."""
    logger.info(
        f"Executing get_epic_by_ref Ref {ref} in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Correct: Get the project object first, then call its helper method
        project = taiga_client.api.projects.get(project_id)
        epic = project.get_epic_by_ref(ref=ref)  # Use Project's method
        if epic is None:
            raise TaigaException(
                f"Epic with ref {ref} not found in project {project_id}")
        return epic.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting epic ref {ref} (project {project_id}): {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting epic ref {ref} (project {project_id}): {e}", exc_info=True)
        raise RuntimeError(f"Server error getting epic by ref: {e}")

# update_epic: Keeping get-modify-update pattern


@mcp.tool("update_epic", description="Updates details of an existing epic.")
def update_epic(session_id: str, epic_id: int, **kwargs) -> Dict[str, Any]:
    """Updates an epic. Pass fields to update as keyword arguments (e.g., subject, description, status_id, assigned_to, color)."""
    logger.info(
        f"Executing update_epic ID {epic_id} for session {session_id[:8]} with data: {kwargs}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        epic = taiga_client.api.epics.get(epic_id)
        allowed_updates = taiga_client.api.epics.instance.allowed_params
        updated = False
        for key, value in kwargs.items():
            if key == "assigned_to" and value is None:
                setattr(epic, key, None)
                updated = True
            elif key in allowed_updates and hasattr(epic, key):
                setattr(epic, key, value)
                updated = True
            else:
                logger.warning(
                    f"Skipping non-updatable/unknown field '{key}' for epic {epic_id}")

        if updated:
            epic.update()
            logger.info(f"Epic {epic_id} updated successfully.")
        else:
            logger.info(
                f"No valid fields provided for update on epic {epic_id}")

        return epic.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating epic {epic_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating epic {epic_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating epic: {e}")


@mcp.tool("delete_epic", description="Deletes an epic by its ID.")
def delete_epic(session_id: str, epic_id: int) -> Dict[str, Any]:
    """Deletes an epic by ID."""
    logger.warning(
        f"Executing delete_epic ID {epic_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        taiga_client.api.epics.delete(epic_id)
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


@mcp.tool("assign_epic_to_user", description="Assigns a specific epic to a specific user.")
def assign_epic_to_user(session_id: str, epic_id: int, user_id: int) -> Dict[str, Any]:
    """Assigns an epic to a user."""
    logger.info(
        f"Executing assign_epic_to_user: Epic {epic_id} -> User {user_id}, session {session_id[:8]}...")
    return update_epic(session_id, epic_id, assigned_to=user_id)


@mcp.tool("unassign_epic_from_user", description="Unassigns a specific epic (sets assigned user to null).")
def unassign_epic_from_user(session_id: str, epic_id: int) -> Dict[str, Any]:
    """Unassigns an epic."""
    logger.info(
        f"Executing unassign_epic_from_user: Epic {epic_id}, session {session_id[:8]}...")
    return update_epic(session_id, epic_id, assigned_to=None)


@mcp.tool("get_epic_statuses", description="Lists the available statuses for epics within a specific project.")
def get_epic_statuses(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the list of epic statuses for a project."""
    logger.info(
        f"Executing get_epic_statuses for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        statuses = taiga_client.api.epic_statuses.list(project=project_id)
        return [s.to_dict() for s in statuses]
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting epic statuses for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting epic statuses for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting epic statuses: {e}")


# --- Milestone (Sprint) Tools ---

@mcp.tool("list_milestones", description="Lists milestones (sprints) within a specific project.")
def list_milestones(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Lists milestones for a project."""
    logger.info(
        f"Executing list_milestones for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        milestones = taiga_client.api.milestones.list(project=project_id)
        return [m.to_dict() for m in milestones]
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing milestones for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing milestones for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing milestones: {e}")


@mcp.tool("create_milestone", description="Creates a new milestone (sprint) within a project.")
def create_milestone(session_id: str, project_id: int, name: str, estimated_start: str, estimated_finish: str) -> Dict[str, Any]:
    """Creates a milestone. Requires project_id, name, estimated_start (YYYY-MM-DD), and estimated_finish (YYYY-MM-DD)."""
    logger.info(
        f"Executing create_milestone '{name}' in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    if not all([name, estimated_start, estimated_finish]):
        raise ValueError(
            "Milestone requires name, estimated_start, and estimated_finish.")
    try:
        # Note: Check python-taiga signature if using positional args
        milestone = taiga_client.api.milestones.create(
            project_id, name, estimated_start, estimated_finish)
        logger.info(
            f"Milestone '{name}' created successfully (ID: {milestone.id}).")
        return milestone.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error creating milestone '{name}': {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error creating milestone '{name}': {e}", exc_info=True)
        raise RuntimeError(f"Server error creating milestone: {e}")


@mcp.tool("get_milestone", description="Gets detailed information about a specific milestone by its ID.")
def get_milestone(session_id: str, milestone_id: int) -> Dict[str, Any]:
    """Retrieves milestone details by ID."""
    logger.info(
        f"Executing get_milestone ID {milestone_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        milestone = taiga_client.api.milestones.get(milestone_id)
        return milestone.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting milestone {milestone_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting milestone {milestone_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting milestone: {e}")


@mcp.tool("update_milestone", description="Updates details of an existing milestone.")
def update_milestone(session_id: str, milestone_id: int, **kwargs) -> Dict[str, Any]:
    """Updates a milestone. Pass fields to update as kwargs (e.g., name, estimated_start, estimated_finish)."""
    logger.info(
        f"Executing update_milestone ID {milestone_id} for session {session_id[:8]} with data: {kwargs}")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Consider get-modify-update pattern
        milestone = taiga_client.api.milestones.get(milestone_id)
        for key, value in kwargs.items():
            if hasattr(milestone, key):
                setattr(milestone, key, value)
        milestone.update()
        logger.info(f"Milestone {milestone_id} updated successfully.")
        return milestone.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error updating milestone {milestone_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error updating milestone {milestone_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error updating milestone: {e}")


@mcp.tool("delete_milestone", description="Deletes a milestone by its ID.")
def delete_milestone(session_id: str, milestone_id: int) -> Dict[str, Any]:
    """Deletes a milestone by ID."""
    logger.warning(
        f"Executing delete_milestone ID {milestone_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        taiga_client.api.milestones.delete(milestone_id)
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


@mcp.tool("get_milestone_stats", description="Gets statistics (total points, completed points, etc.) for a specific milestone.")
def get_milestone_stats(session_id: str, milestone_id: int) -> Dict[str, Any]:
    """Retrieves statistics for a milestone."""
    logger.info(
        f"Executing get_milestone_stats ID {milestone_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Correct: Get the milestone instance first, then call its stats() method
        milestone = taiga_client.api.milestones.get(milestone_id)
        stats = milestone.stats()
        # The stats object might already be a dict, or need .to_dict() if it's some custom object
        # Ensure serializable
        return stats if isinstance(stats, dict) else {"stats": stats}
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting stats for milestone {milestone_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting stats for milestone {milestone_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting milestone stats: {e}")


# --- User Management Tools ---

@mcp.tool("get_project_members", description="Lists members of a specific project.")
def get_project_members(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the list of members for a project."""
    logger.info(
        f"Executing get_project_members for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Project object has a list_members method
        project = taiga_client.api.projects.get(project_id)
        members = project.list_members()
        return [m.to_dict() for m in members]
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting members for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting members for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting project members: {e}")


@mcp.tool("invite_project_user", description="Invites a user to a project by email with a specific role.")
def invite_project_user(session_id: str, project_id: int, email: str, role_id: int) -> Dict[str, Any]:
    """Invites a user via email to join the project with the specified role ID."""
    logger.info(
        f"Executing invite_project_user {email} to project {project_id} (role {role_id}), session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    if not email:
        raise ValueError("Email cannot be empty.")
    try:
        # Correct: Use the memberships API endpoint with correct arg order/names from model
        # Memberships.create(self, project, email, role, **attrs)
        membership = taiga_client.api.memberships.create(
            project=project_id, email=email, role=role_id)
        logger.info(f"Invitation sent to {email} for project {project_id}.")
        # The returned object might be the membership details or just status
        return membership.to_dict() if hasattr(membership, 'to_dict') else {"status": "invited", "email": email}
    except TaigaException as e:
        logger.error(
            f"Taiga API error inviting user {email} to project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error inviting user {email} to project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error inviting user: {e}")


# --- Wiki Tools ---

@mcp.tool("list_wiki_pages", description="Lists wiki pages within a specific project.")
def list_wiki_pages(session_id: str, project_id: int) -> List[Dict[str, Any]]:
    """Lists wiki pages for a project."""
    logger.info(
        f"Executing list_wiki_pages for project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        pages = taiga_client.api.wiki_pages.list(project=project_id)
        return [p.to_dict() for p in pages]
    except TaigaException as e:
        logger.error(
            f"Taiga API error listing wiki pages for project {project_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error listing wiki pages for project {project_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error listing wiki pages: {e}")


@mcp.tool("get_wiki_page", description="Gets a specific wiki page by its ID.")
def get_wiki_page(session_id: str, wiki_page_id: int) -> Dict[str, Any]:
    """Retrieves wiki page details by ID."""
    logger.info(
        f"Executing get_wiki_page ID {wiki_page_id} for session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        page = taiga_client.api.wiki_pages.get(wiki_page_id)
        return page.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting wiki page {wiki_page_id}: {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting wiki page {wiki_page_id}: {e}", exc_info=True)
        raise RuntimeError(f"Server error getting wiki page: {e}")


@mcp.tool("get_wiki_page_by_slug", description="Gets a specific wiki page by its slug within a project.")
def get_wiki_page_by_slug(session_id: str, project_id: int, slug: str) -> Dict[str, Any]:
    """Retrieves wiki page details by project ID and slug."""
    logger.info(
        f"Executing get_wiki_page_by_slug '{slug}' in project {project_id}, session {session_id[:8]}...")
    taiga_client = _get_authenticated_client(session_id)
    try:
        # Check: WikiPages model doesn't show get_by_slug. Assume get(slug=..., project=...) is correct.
        page = taiga_client.api.wikipages.get(slug=slug, project=project_id)
        return page.to_dict()
    except TaigaException as e:
        logger.error(
            f"Taiga API error getting wiki page by slug '{slug}' (project {project_id}): {e}", exc_info=False)
        raise e
    except Exception as e:
        logger.error(
            f"Unexpected error getting wiki page by slug '{slug}' (project {project_id}): {e}", exc_info=True)
        raise RuntimeError(f"Server error getting wiki page by slug: {e}")


# --- Session Management Tools ---

@mcp.tool("logout", description="Invalidates the current session_id.")
def logout(session_id: str) -> Dict[str, Any]:
    """Logs out the current session, invalidating the session_id."""
    logger.info(f"Executing logout for session {session_id[:8]}...")
    # Remove from dict, return None if not found
    client = active_sessions.pop(session_id, None)
    if client:
        logger.info(f"Session {session_id[:8]} logged out successfully.")
        # Optionally call any Taiga logout endpoint if the library supports/requires it
        # try:
        #     client.api.auth_logout() # Check if such a method exists
        # except Exception: pass # Ignore errors on logout
        return {"status": "logged_out", "session_id": session_id}
    else:
        logger.warning(
            f"Attempted to log out non-existent session: {session_id}")
        # Raise error or return specific status? Let's return status for idempotency.
        return {"status": "session_not_found", "session_id": session_id}


@mcp.tool("session_status", description="Checks if the provided session_id is currently active and valid.")
def session_status(session_id: str) -> Dict[str, Any]:
    """Checks the validity of the current session_id."""
    logger.debug(
        f"Executing session_status check for session {session_id[:8]}...")
    client = active_sessions.get(session_id)
    if client and client.is_authenticated:
        # Optionally make a lightweight API call like `me()` to ensure token is still valid
        try:
            me = client.api.me()
            logger.debug(
                f"Session {session_id[:8]} is active for user {me.username}.")
            return {"status": "active", "session_id": session_id, "username": me.username}
        except TaigaException:
            logger.warning(
                f"Session {session_id[:8]} found but token seems invalid.")
            # Clean up invalid session?
            active_sessions.pop(session_id, None)
            return {"status": "inactive", "reason": "token_invalid", "session_id": session_id}
    # Client exists but not authenticated (shouldn't happen with current logic)
    elif client:
        logger.warning(
            f"Session {session_id[:8]} exists but client is not authenticated.")
        return {"status": "inactive", "reason": "not_authenticated", "session_id": session_id}
    else:
        logger.debug(f"Session {session_id[:8]} not found.")
        return {"status": "inactive", "reason": "not_found", "session_id": session_id}


# --- Run the server ---
if __name__ == "__main__":
    mcp.run()
