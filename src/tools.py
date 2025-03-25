from mcp.server.fastmcp import FastMCP
from taiga_client import TaigaClient, active_sessions
import logging
import time
from config import Settings
import json

# Configure logging
logger = logging.getLogger('taiga_mcp')

# Initialize the MCP server
mcp = FastMCP("Taiga Bridge")

# Authentication Tools
@mcp.tool("login", description="Authenticate with Taiga and obtain a session ID. This tool validates user credentials and returns a session ID that must be used for all subsequent operations. The session ID expires after a configurable time period.")
def login(username: str, password: str, host: str = None) -> dict:
    """Authenticate with Taiga and get a session ID"""
    logger.info(f"Login attempt for user: {username}, host: {host or 'default'}")
    try:
        client = TaigaClient(host=host)
        session_id = client.authenticate(username, password)
        logger.info(f"Login successful for user: {username}")
        return {"session_id": session_id}
    except Exception as e:
        logger.error(f"Login failed for user: {username}. Error: {str(e)}")
        raise

@mcp.tool("logout", description="End an active Taiga session. This invalidates the session ID and removes it from active sessions. Any further attempts to use the session ID will fail.")
def logout(session_id: str) -> dict:
    """End a session"""
    logger.info(f"Logout request for session: {session_id}")
    try:
        TaigaClient.logout(session_id)
        logger.info(f"Logout successful for session: {session_id}")
        return {"status": "logged out"}
    except Exception as e:
        logger.error(f"Logout failed for session: {session_id}. Error: {str(e)}")
        raise

@mcp.tool("session_status", description="Check if a session is still valid and get information about its creation and expiration time.")
def session_status(session_id: str) -> dict:
    logger.info(f"Tool: Checking session status for session: {session_id}")
    try:
        # Check if session exists and is valid
        if session_id not in active_sessions:
            return {
                "status": "invalid",
                "message": "Session not found"
            }
        
        # Get session data
        session_data = active_sessions[session_id]
        created_at = session_data["created_at"]
        
        # Calculate time remaining
        settings = Settings()
        current_time = time.time()
        time_remaining = settings.SESSION_EXPIRY - (current_time - created_at)
        
        if time_remaining <= 0:
            # Session has expired, clean it up
            del active_sessions[session_id]
            return {
                "status": "expired",
                "message": "Session has expired",
                "created_at": created_at,
                "expired_at": created_at + settings.SESSION_EXPIRY
            }
        
        return {
            "status": "active",
            "message": "Session is valid",
            "created_at": created_at,
            "expires_at": created_at + settings.SESSION_EXPIRY,
            "time_remaining_seconds": int(time_remaining)
        }
    except Exception as e:
        logger.error(f"Tool: Failed to check session status. Error: {str(e)}")
        raise

# Status Type Tools
@mcp.tool("list_task_statuses", description="List all available task statuses for a project. Returns status information including ID, name, color, and whether it's a closed status.")
def get_task_statuses(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching task statuses for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_task_statuses(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} task statuses")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch task statuses. Error: {str(e)}")
        raise

@mcp.tool("list_epic_statuses", description="List all available epic statuses for a project. Returns status information including ID, name, color, and whether it's a closed status.")
def get_epic_statuses(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching epic statuses for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_epic_statuses(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} epic statuses")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch epic statuses. Error: {str(e)}")
        raise

@mcp.tool("list_user_story_statuses", description="List all available user story statuses for a project. Returns status information including ID, name, color, and whether it's a closed status.")
def get_user_story_statuses(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching user story statuses for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_user_story_statuses(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} user story statuses")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch user story statuses. Error: {str(e)}")
        raise

@mcp.tool("list_issue_statuses", description="List all available issue statuses for a project. Returns status information including ID, name, color, and whether it's a closed status.")
def get_issue_statuses(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching issue statuses for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_issue_statuses(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} issue statuses")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch issue statuses. Error: {str(e)}")
        raise

@mcp.tool("list_issue_types", description="List all available issue types for a project. Returns type information including ID, name, and color.")
def get_issue_types(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching issue types for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_issue_types(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} issue types")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch issue types. Error: {str(e)}")
        raise

@mcp.tool("list_issue_priorities", description="List all available issue priorities for a project. Returns priority information including ID, name, and color.")
def get_issue_priorities(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching issue priorities for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_issue_priorities(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} issue priorities")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch issue priorities. Error: {str(e)}")
        raise

@mcp.tool("list_issue_severities", description="List all available issue severities for a project. Returns severity information including ID, name, and color.")
def get_issue_severities(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching issue severities for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_issue_severities(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} issue severities")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch issue severities. Error: {str(e)}")
        raise

# User Management Tools
@mcp.tool("list_project_members", description="List all members of a project. Returns member information including username, full name, email, and role.")
def get_project_members(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching project members for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_project_members(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} project members")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch project members. Error: {str(e)}")
        raise

@mcp.tool("list_project_roles", description="List all available roles in a project. Returns role information including name and associated permissions.")
def get_project_roles(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching project roles for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_project_roles(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} project roles")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch project roles. Error: {str(e)}")
        raise

@mcp.tool("invite_user", description="Invite a user to join a project with a specific role. Requires the user's email and the role ID they should be assigned.")
def invite_project_user(session_id: str, project_id: int, email: str, role_id: int) -> dict:
    logger.info(f"Tool: Inviting user {email} to project {project_id} with role {role_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.invite_user(project_id, email, role_id)
        logger.info(f"Tool: Successfully invited user {email} to project")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to invite user. Error: {str(e)}")
        raise

# Assignment Tools
@mcp.tool("assign_epic", description="Assign an epic to a specific user. Requires the epic ID and the user ID to assign it to.")
def assign_epic_to_user(session_id: str, epic_id: int, user_id: int) -> dict:
    logger.info(f"Tool: Assigning epic {epic_id} to user {user_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.assign_epic(epic_id, user_id)
        logger.info(f"Tool: Successfully assigned epic {epic_id} to user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to assign epic. Error: {str(e)}")
        raise

@mcp.tool("assign_user_story", description="Assign a user story to a specific user. Requires the user story ID and the user ID to assign it to.")
def assign_user_story_to_user(session_id: str, user_story_id: int, user_id: int) -> dict:
    logger.info(f"Tool: Assigning user story {user_story_id} to user {user_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.assign_user_story(user_story_id, user_id)
        logger.info(f"Tool: Successfully assigned user story {user_story_id} to user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to assign user story. Error: {str(e)}")
        raise

@mcp.tool("assign_task", description="Assign a task to a specific user. Requires the task ID and the user ID to assign it to.")
def assign_task_to_user(session_id: str, task_id: int, user_id: int) -> dict:
    logger.info(f"Tool: Assigning task {task_id} to user {user_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.assign_task(task_id, user_id)
        logger.info(f"Tool: Successfully assigned task {task_id} to user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to assign task. Error: {str(e)}")
        raise

@mcp.tool("assign_issue", description="Assign an issue to a specific user. Requires the issue ID and the user ID to assign it to.")
def assign_issue_to_user(session_id: str, issue_id: int, user_id: int) -> dict:
    logger.info(f"Tool: Assigning issue {issue_id} to user {user_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.assign_issue(issue_id, user_id)
        logger.info(f"Tool: Successfully assigned issue {issue_id} to user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to assign issue. Error: {str(e)}")
        raise

# List Tools
@mcp.tool("list_projects", description="List all projects accessible to the authenticated user. Returns basic project information including ID, name, description, and other metadata.")
def get_projects(session_id: str) -> list:
    logger.info(f"Tool: Fetching projects for session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_projects()
        logger.info(f"Tool: Successfully fetched {len(result)} projects")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch projects. Error: {str(e)}")
        raise

@mcp.tool("list_project_epics", description="List all epics within a specific project. Requires project_id parameter to identify the target project.")
def get_project_epics(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching epics for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_epics(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} epics")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch epics. Error: {str(e)}")
        raise

@mcp.tool("list_epics", description="List all epics across all accessible projects. Returns comprehensive epic information including associated projects and user stories.")
def get_epics(session_id: str) -> list:
    logger.info(f"Tool: Fetching all epics for session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_epics()
        logger.info(f"Tool: Successfully fetched {len(result)} epics")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch epics. Error: {str(e)}")
        raise

@mcp.tool("list_project_user_stories", description="List all user stories within a specific project. Filtered by project_id to show only stories belonging to that project.")
def get_project_user_stories(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching user stories for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_user_stories(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} user stories")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch user stories. Error: {str(e)}")
        raise

@mcp.tool("list_sprint_user_stories", description="List all user stories assigned to a specific sprint/milestone. Shows stories planned for the given sprint iteration.")
def get_sprint_user_stories(session_id: str, milestone_id: int) -> list:
    logger.info(f"Tool: Fetching user stories for sprint {milestone_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_user_stories(milestone_id=milestone_id)
        logger.info(f"Tool: Successfully fetched {len(result)} user stories")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch user stories. Error: {str(e)}")
        raise

@mcp.tool("list_epic_user_stories", description="List all user stories associated with a specific epic. Shows the breakdown of an epic into its constituent user stories.")
def get_epic_user_stories(session_id: str, epic_id: int) -> list:
    logger.info(f"Tool: Fetching user stories for epic {epic_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_user_stories(epic_id=epic_id)
        logger.info(f"Tool: Successfully fetched {len(result)} user stories")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch user stories. Error: {str(e)}")
        raise

@mcp.tool("list_user_stories", description="List all user stories across all accessible projects. Returns comprehensive story information including status, points, and assignments.")
def get_user_stories(session_id: str) -> list:
    logger.info(f"Tool: Fetching all user stories for session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_user_stories()
        logger.info(f"Tool: Successfully fetched {len(result)} user stories")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch user stories. Error: {str(e)}")
        raise

@mcp.tool("list_project_tasks", description="List all tasks within a specific project. Shows detailed task information for the given project.")
def get_project_tasks(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching tasks for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_tasks(project_id=project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} tasks")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch tasks. Error: {str(e)}")
        raise

@mcp.tool("list_user_story_tasks", description="List all tasks associated with a specific user story. Shows the breakdown of a user story into its component tasks.")
def get_user_story_tasks(session_id: str, user_story_id: int) -> list:
    logger.info(f"Tool: Fetching tasks for user story {user_story_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_tasks(user_story_id=user_story_id)
        logger.info(f"Tool: Successfully fetched {len(result)} tasks")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch tasks. Error: {str(e)}")
        raise

@mcp.tool("list_tasks", description="List all tasks across all accessible projects. Returns comprehensive task information including status, assignee, and related user story.")
def get_tasks(session_id: str) -> list:
    logger.info(f"Tool: Fetching all tasks for session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_tasks()
        logger.info(f"Tool: Successfully fetched {len(result)} tasks")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch tasks. Error: {str(e)}")
        raise

@mcp.tool("list_project_issues", description="List all issues within a specific project. Shows bugs, questions, and enhancement requests for the given project.")
def get_project_issues(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching issues for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_issues(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} issues")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch issues. Error: {str(e)}")
        raise

@mcp.tool("list_issues", description="List all issues across all accessible projects. Returns comprehensive issue information including type, severity, priority, and status.")
def get_issues(session_id: str) -> list:
    logger.info(f"Tool: Fetching all issues for session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_issues()
        logger.info(f"Tool: Successfully fetched {len(result)} issues")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch issues. Error: {str(e)}")
        raise

@mcp.tool("list_project_sprints", description="List all sprints/milestones within a specific project. Shows iteration planning information for the given project.")
def get_project_sprints(session_id: str, project_id: int) -> list:
    logger.info(f"Tool: Fetching sprints for project {project_id}, session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_sprints(project_id)
        logger.info(f"Tool: Successfully fetched {len(result)} sprints")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch sprints. Error: {str(e)}")
        raise

@mcp.tool("list_sprints", description="List all sprints across all accessible projects. Returns comprehensive sprint information including dates, status, and workload stats.")
def get_sprints(session_id: str) -> list:
    logger.info(f"Tool: Fetching all sprints for session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.list_sprints()
        logger.info(f"Tool: Successfully fetched {len(result)} sprints")
        return result
    except Exception as e:
        logger.error(f"Tool: Failed to fetch sprints. Error: {str(e)}")
        raise

# CRUD Tools for Projects
@mcp.tool("create_project", description="Create a new Taiga project. Initializes a project with the given name and description, setting up default configurations for epics, user stories, tasks, and issues.")
def create_project(session_id: str, name: str, description: str = "") -> dict:
    logger.info(f"Creating project. Session: {session_id}, Name: {name}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.create_project(name, description)
        logger.info(f"Successfully created project: {name}")
        return result
    except Exception as e:
        logger.error(f"Failed to create project {name}. Error: {str(e)}")
        raise

@mcp.tool("update_project", description="Update an existing project's details. Supports modifying project attributes like name, description, and other configurable settings.")
def update_project(session_id: str, project_id: int, **kwargs) -> dict:
    logger.info(f"Updating project {project_id}. Session: {session_id}, Updates: {json.dumps(kwargs)}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.update_project(project_id, **kwargs)
        logger.info(f"Successfully updated project {project_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to update project {project_id}. Error: {str(e)}")
        raise

@mcp.tool("delete_project", description="Delete an existing project. This permanently removes the project and all its associated data (epics, stories, tasks, issues).")
def delete_project(session_id: str, project_id: int) -> dict:
    logger.info(f"Deleting project {project_id}. Session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.delete_project(project_id)
        logger.info(f"Successfully deleted project {project_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}. Error: {str(e)}")
        raise

# CRUD Tools for Epics
@mcp.tool("create_epic", description="Create a new epic within a project. Epics are large user stories that can be broken down into smaller stories. Requires project_id and subject.")
def create_epic(session_id: str, project_id: int, subject: str, description: str = None) -> dict:
    logger.info(f"Creating epic in project {project_id}. Session: {session_id}, Subject: {subject}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.create_epic(project_id, subject, description)
        logger.info(f"Successfully created epic: {subject}")
        return result
    except Exception as e:
        logger.error(f"Failed to create epic {subject}. Error: {str(e)}")
        raise

@mcp.tool("update_epic", description="Update an existing epic's details. Supports modifying epic attributes like subject, description, and status.")
def update_epic(session_id: str, epic_id: int, subject: str = None, description: str = None) -> dict:
    logger.info(f"Updating epic {epic_id}. Session: {session_id}, Updates: subject={subject}, description={description}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.update_epic(epic_id, subject=subject, description=description)
        logger.info(f"Successfully updated epic {epic_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to update epic {epic_id}. Error: {str(e)}")
        raise

@mcp.tool("delete_epic", description="Delete an existing epic. This removes the epic and optionally its associated user stories (based on configuration).")
def delete_epic(session_id: str, epic_id: int) -> dict:
    logger.info(f"Deleting epic {epic_id}. Session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.delete_epic(epic_id)
        logger.info(f"Successfully deleted epic {epic_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to delete epic {epic_id}. Error: {str(e)}")
        raise

# CRUD Tools for User Stories
@mcp.tool("create_user_story", description="Create a new user story within a project. Stories can be associated with epics and sprints, and broken down into tasks.")
def create_user_story(session_id: str, project_id: int, subject: str, description: str = None, milestone_id: int = None) -> dict:
    logger.info(f"Creating user story in project {project_id}. Session: {session_id}, Subject: {subject}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.create_user_story(project_id, subject, description, milestone_id)
        logger.info(f"Successfully created user story: {subject}")
        return result
    except Exception as e:
        logger.error(f"Failed to create user story {subject}. Error: {str(e)}")
        raise

@mcp.tool("update_user_story", description="Update an existing user story. Supports modifying story attributes including subject, description, status, and sprint assignment.")
def update_user_story(session_id: str, user_story_id: int, subject: str = None, description: str = None, 
                     milestone_id: int = None, status_id: int = None) -> dict:
    logger.info(f"Updating user story {user_story_id}. Session: {session_id}, Updates: subject={subject}, description={description}, milestone_id={milestone_id}, status_id={status_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.update_user_story(user_story_id, subject=subject, description=description, 
                                        milestone=milestone_id, status=status_id)
        logger.info(f"Successfully updated user story {user_story_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to update user story {user_story_id}. Error: {str(e)}")
        raise

@mcp.tool("delete_user_story", description="Delete an existing user story. This removes the story and all its associated tasks.")
def delete_user_story(session_id: str, user_story_id: int) -> dict:
    logger.info(f"Deleting user story {user_story_id}. Session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.delete_user_story(user_story_id)
        logger.info(f"Successfully deleted user story {user_story_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to delete user story {user_story_id}. Error: {str(e)}")
        raise

# CRUD Tools for Tasks
@mcp.tool("create_task", description="Create a new task associated with a user story. Tasks represent concrete work items that need to be completed.")
def create_task(session_id: str, user_story_id: int, subject: str, description: str = None, status_id: int = None) -> dict:
    logger.info(f"Creating task for user story {user_story_id}. Session: {session_id}, Subject: {subject}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.create_task(user_story_id, subject, description, status_id)
        logger.info(f"Successfully created task: {subject}")
        return result
    except Exception as e:
        logger.error(f"Failed to create task {subject}. Error: {str(e)}")
        raise

@mcp.tool("update_task", description="Update an existing task. Supports modifying task attributes including subject, description, status, and user story association.")
def update_task(session_id: str, task_id: int, subject: str = None, description: str = None, 
               status_id: int = None, user_story_id: int = None) -> dict:
    logger.info(f"Updating task {task_id}. Session: {session_id}, Updates: subject={subject}, description={description}, status_id={status_id}, user_story_id={user_story_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.update_task(task_id, subject=subject, description=description, 
                                  status=status_id, user_story=user_story_id)
        logger.info(f"Successfully updated task {task_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to update task {task_id}. Error: {str(e)}")
        raise

@mcp.tool("delete_task", description="Delete an existing task. This permanently removes the task from its associated user story.")
def delete_task(session_id: str, task_id: int) -> dict:
    logger.info(f"Deleting task {task_id}. Session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.delete_task(task_id)
        logger.info(f"Successfully deleted task {task_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to delete task {task_id}. Error: {str(e)}")
        raise

# CRUD Tools for Issues
@mcp.tool("create_issue", description="Create a new issue within a project. Issues can represent bugs, questions, or enhancement requests with customizable attributes.")
def create_issue(session_id: str, project_id: int, subject: str, description: str = None, 
               priority_id: int = None, status_id: int = None, 
               type_id: int = None, severity_id: int = None) -> dict:
    logger.info(f"Creating issue in project {project_id}. Session: {session_id}, Subject: {subject}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.create_issue(project_id, subject, description, 
                                   priority_id, status_id, type_id, severity_id)
        logger.info(f"Successfully created issue: {subject}")
        return result
    except Exception as e:
        logger.error(f"Failed to create issue {subject}. Error: {str(e)}")
        raise

@mcp.tool("update_issue", description="Update an existing issue. Supports modifying issue attributes including subject, description, priority, status, type, and severity.")
def update_issue(session_id: str, issue_id: int, subject: str = None, description: str = None, 
               priority_id: int = None, status_id: int = None, 
               type_id: int = None, severity_id: int = None) -> dict:
    logger.info(f"Updating issue {issue_id}. Session: {session_id}, Updates: subject={subject}, description={description}, priority_id={priority_id}, status_id={status_id}, type_id={type_id}, severity_id={severity_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.update_issue(issue_id, subject=subject, description=description, 
                                   priority=priority_id, status=status_id, 
                                   type=type_id, severity=severity_id)
        logger.info(f"Successfully updated issue {issue_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to update issue {issue_id}. Error: {str(e)}")
        raise

@mcp.tool("delete_issue", description="Delete an existing issue. This permanently removes the issue from the project.")
def delete_issue(session_id: str, issue_id: int) -> dict:
    logger.info(f"Deleting issue {issue_id}. Session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.delete_issue(issue_id)
        logger.info(f"Successfully deleted issue {issue_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to delete issue {issue_id}. Error: {str(e)}")
        raise

# CRUD Tools for Sprints
@mcp.tool("create_sprint", description="Create a new sprint/milestone within a project. Sprints represent time-boxed iterations for completing user stories.")
def create_sprint(session_id: str, project_id: int, name: str, start_date: str, end_date: str) -> dict:
    logger.info(f"Creating sprint in project {project_id}. Session: {session_id}, Name: {name}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.create_sprint(project_id, name, start_date, end_date)
        logger.info(f"Successfully created sprint: {name}")
        return result
    except Exception as e:
        logger.error(f"Failed to create sprint {name}. Error: {str(e)}")
        raise

@mcp.tool("update_sprint", description="Update an existing sprint. Supports modifying sprint attributes including name and date range.")
def update_sprint(session_id: str, sprint_id: int, name: str = None, start_date: str = None, end_date: str = None) -> dict:
    logger.info(f"Updating sprint {sprint_id}. Session: {session_id}, Updates: name={name}, start_date={start_date}, end_date={end_date}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.update_sprint(sprint_id, name=name, 
                                    estimated_start=start_date, 
                                    estimated_finish=end_date)
        logger.info(f"Successfully updated sprint {sprint_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to update sprint {sprint_id}. Error: {str(e)}")
        raise

@mcp.tool("delete_sprint", description="Delete an existing sprint. This removes the sprint while preserving its user stories (they become unassigned).")
def delete_sprint(session_id: str, sprint_id: int) -> dict:
    logger.info(f"Deleting sprint {sprint_id}. Session: {session_id}")
    try:
        client = TaigaClient.get_client_by_session(session_id)
        result = client.delete_sprint(sprint_id)
        logger.info(f"Successfully deleted sprint {sprint_id}")
        return result
    except Exception as e:
        logger.error(f"Failed to delete sprint {sprint_id}. Error: {str(e)}")
        raise
