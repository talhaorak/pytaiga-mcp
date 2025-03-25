from taiga import TaigaAPI
from config import Settings
import os
import uuid
import time
import logging
import httpx
from typing import Optional, Dict, List, Any, TypedDict, Union
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel, Field, validator


# Configure logging
logger = logging.getLogger('taiga_mcp')


# Session storage with type annotations
class SessionData(TypedDict):
    client: 'TaigaClient'
    created_at: float


# Dictionary to store authenticated sessions with their creation timestamps
active_sessions: Dict[str, SessionData] = {}


# Base exception class for Taiga client
class TaigaClientError(Exception):
    """Base exception for Taiga client errors."""
    pass


# Data models for API requests and responses
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)


class UserStoryCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    milestone: Optional[int] = Field(None)


class TaskCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    user_story: Optional[int] = Field(None)
    status: Optional[int] = Field(None)


class IssueCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    priority: Optional[int] = Field(None)
    status: Optional[int] = Field(None)
    type: Optional[int] = Field(None)
    severity: Optional[int] = Field(None)


class ApiResponse(BaseModel):
    """Standard response model for API operations"""
    status: str
    message: Optional[str] = None
    data: Optional[Any] = None


def cleanup_expired_sessions() -> None:
    """Remove expired sessions from active_sessions dictionary."""
    current_time = time.time()
    settings = Settings()
    expired_sessions = [
        session_id for session_id, session_data in active_sessions.items()
        if current_time - session_data["created_at"] > settings.SESSION_EXPIRY
    ]
    for session_id in expired_sessions:
        logger.info(f"Removing expired session: {session_id}")
        del active_sessions[session_id]


def handle_api_error(func):
    """Decorator to standardize error handling."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"API error in {func.__name__}: {str(e)}")
            return {
                "status": "error",
                "error_type": type(e).__name__,
                "message": str(e)
            }
    return wrapper


class TaigaClient:
    def __init__(self, host: Optional[str] = None):
        """Initialize Taiga client.
        
        Args:
            host: Optional Taiga API host URL. If not provided, uses settings.
        """
        self.settings = Settings()
        if host:
            self.settings.TAIGA_API_URL = host
        self.api: Optional[TaigaAPI] = None
        
        # Initialize HTTP client with connection pooling
        self.http_client = httpx.Client(
            timeout=self.settings.REQUEST_TIMEOUT,
            limits=httpx.Limits(
                max_keepalive_connections=self.settings.MAX_KEEPALIVE_CONNECTIONS,
                max_connections=self.settings.MAX_CONNECTIONS
            )
        )
        
        # Request count for rate limiting
        self.request_count = 0
        self.request_count_reset_time = time.time() + 60  # Reset count every minute
    
    def __del__(self):
        """Clean up resources when the client is destroyed."""
        if hasattr(self, 'http_client') and self.http_client:
            self.http_client.close()
    
    def _check_rate_limit(self) -> None:
        """Check if the client is exceeding the rate limit."""
        current_time = time.time()
        
        # Reset request count if needed
        if current_time > self.request_count_reset_time:
            self.request_count = 0
            self.request_count_reset_time = current_time + 60
        
        # Check if rate limit exceeded
        if self.request_count >= self.settings.RATE_LIMIT_REQUESTS:
            raise TaigaClientError(f"Rate limit exceeded: {self.settings.RATE_LIMIT_REQUESTS} requests per minute")
        
        # Increment request count
        self.request_count += 1
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def make_api_call(self, func, *args, **kwargs):
        """Make API call with retry mechanism.
        
        Args:
            func: Function to call
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            The result of the function call
        """
        self._check_rate_limit()
        return func(*args, **kwargs)

    def authenticate(self, username: str, password: str, host: Optional[str] = None) -> Dict[str, Any]:
        """Authenticate with Taiga API using provided credentials
        
        Args:
            username: Taiga username
            password: Taiga password
            host: Optional Taiga API host URL
            
        Returns:
            Dict containing session information
        """
        try:
            # Clean up expired sessions first
            cleanup_expired_sessions()
            
            # Use provided host or fall back to settings
            taiga_host = host or self.settings.TAIGA_API_URL

            # Create and authenticate a Taiga API client
            self.api = TaigaAPI(host=taiga_host)
            self.api.auth(username=username, password=password)

            # Generate a session ID for this authenticated client
            session_id = str(uuid.uuid4())
            active_sessions[session_id] = {
                "client": self,
                "created_at": time.time()
            }

            # Session information
            expiry_seconds = self.settings.SESSION_EXPIRY

            return {
                "session_id": session_id,
                "status": "authenticated",
                "message": "Successfully authenticated with Taiga API",
                "expires_in_seconds": expiry_seconds
            }
        except Exception as e:
            logger.error(f"Authentication failed for user {username}: {str(e)}")
            return {"status": "error", "message": f"Authentication failed: {str(e)}"}

    @staticmethod
    def get_client_by_session(session_id: str) -> 'TaigaClient':
        """Retrieve a TaigaClient instance by session ID
        
        Args:
            session_id: Session ID to look up
            
        Returns:
            The TaigaClient instance associated with the session
            
        Raises:
            ValueError: If the session ID is invalid or expired
        """
        if session_id not in active_sessions:
            logger.warning(f"Invalid session ID: {session_id}")
            raise ValueError(f"Invalid or expired session ID: {session_id}")

        # Get the session data
        session_data = active_sessions[session_id]
        created_at = session_data["created_at"]
        client = session_data["client"]

        # Check if session has expired
        current_time = time.time()
        if current_time - created_at > client.settings.SESSION_EXPIRY:
            # Remove the expired session
            logger.info(f"Session {session_id} has expired")
            del active_sessions[session_id]
            raise ValueError(
                f"Session {session_id} has expired. Please login again.")

        return client

    @staticmethod
    def logout(session_id: str) -> Dict[str, str]:
        """Remove a session from active sessions
        
        Args:
            session_id: Session ID to remove
            
        Returns:
            Dict containing status and message
        """
        if session_id in active_sessions:
            del active_sessions[session_id]
            logger.info(f"Logged out session: {session_id}")
            return {"status": "success", "message": "Logged out successfully"}
        logger.warning(f"Logout attempt with invalid session ID: {session_id}")
        return {"status": "error", "message": "Invalid session ID"}

    # Projects CRUD
    @handle_api_error
    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects available to the authenticated user.
        
        Returns:
            List of project dictionaries with id and name
        """
        projects = self.make_api_call(self.api.projects.list)
        return [{"id": p.id, "name": p.name} for p in projects]

    @handle_api_error
    def get_project(self, project_id: int) -> Dict[str, Any]:
        """Get details of a specific project.
        
        Args:
            project_id: The ID of the project to retrieve
            
        Returns:
            Project details dictionary
        """
        project = self.make_api_call(self.api.projects.get, project_id)
        return {
            "id": project.id, 
            "name": project.name, 
            "description": project.description,
            "is_private": getattr(project, "is_private", None),
            "created_date": getattr(project, "created_date", None),
            "owner": getattr(project, "owner", {}).get("id") if hasattr(project, "owner") else None
        }

    @handle_api_error
    def create_project(self, project_data: Union[ProjectCreate, Dict[str, Any]]) -> Dict[str, Any]:
        """Create a new project.
        
        Args:
            project_data: ProjectCreate model or dictionary with project details
            
        Returns:
            Created project details
        """
        # Convert to ProjectCreate if dict
        if isinstance(project_data, dict):
            project_data = ProjectCreate(**project_data)
            
        project = self.make_api_call(
            self.api.projects.create,
            name=project_data.name,
            description=project_data.description or ""
        )
        
        return {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": "created"
        }

    @handle_api_error
    def update_project(self, project_id: int, **kwargs) -> Dict[str, Any]:
        """Update an existing project.
        
        Args:
            project_id: The ID of the project to update
            **kwargs: Project attributes to update
            
        Returns:
            Updated project details
        """
        project = self.make_api_call(self.api.projects.get, project_id)
        updated_project = self.make_api_call(project.update, **kwargs)
        
        return {
            "id": updated_project.id,
            "name": updated_project.name,
            "description": updated_project.description,
            "status": "updated"
        }

    @handle_api_error
    def delete_project(self, project_id: int) -> Dict[str, str]:
        """Delete a project.
        
        Args:
            project_id: The ID of the project to delete
            
        Returns:
            Status dictionary
        """
        project = self.make_api_call(self.api.projects.get, project_id)
        self.make_api_call(project.delete)
        return {"status": "deleted", "message": f"Project {project_id} successfully deleted"}

    # Epics CRUD
    @handle_api_error
    def list_epics(self, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List epics, optionally filtered by project.
        
        Args:
            project_id: Optional project ID to filter epics
            
        Returns:
            List of epic dictionaries
        """
        if project_id:
            project = self.make_api_call(self.api.projects.get, project_id)
            epics = self.make_api_call(project.list_epics)
        else:
            epics = self.make_api_call(self.api.epics.list)
        
        return [{
            "id": e.id, 
            "subject": e.subject, 
            "description": getattr(e, "description", ""),
            "project": getattr(e, "project", None),
            "status": getattr(e, "status", None),
            "created_date": getattr(e, "created_date", None),
            "assigned_to": getattr(e, "assigned_to", None)
        } for e in epics]

    @handle_api_error
    def get_epic(self, epic_id: int) -> Dict[str, Any]:
        """Get details of a specific epic.
        
        Args:
            epic_id: ID of the epic to retrieve
            
        Returns:
            Epic details dictionary
        """
        epic = self.make_api_call(self.api.epics.get, epic_id)
        return {
            "id": epic.id, 
            "subject": epic.subject, 
            "description": getattr(epic, "description", ""),
            "project": getattr(epic, "project", None),
            "status": getattr(epic, "status", None),
            "created_date": getattr(epic, "created_date", None),
            "assigned_to": getattr(epic, "assigned_to", None)
        }

    @handle_api_error
    def create_epic(self, project_id: int, subject: str, description: Optional[str] = None) -> Dict[str, Any]:
        """Create a new epic in a project.
        
        Args:
            project_id: Project ID where the epic will be created
            subject: Epic title/subject
            description: Optional epic description
            
        Returns:
            Created epic details
        """
        project = self.make_api_call(self.api.projects.get, project_id)
        epic = self.make_api_call(
            project.add_epic,
            subject=subject,
            description=description or ""
        )
        
        return {
            "id": epic.id,
            "subject": epic.subject,
            "description": getattr(epic, "description", ""),
            "project": getattr(epic, "project", None),
            "status": "created"
        }

    @handle_api_error
    def update_epic(self, epic_id: int, **kwargs) -> Dict[str, Any]:
        """Update an existing epic.
        
        Args:
            epic_id: ID of the epic to update
            **kwargs: Epic attributes to update
            
        Returns:
            Updated epic details
        """
        epic = self.make_api_call(self.api.epics.get, epic_id)
        updated_epic = self.make_api_call(epic.update, **kwargs)
        
        return {
            "id": updated_epic.id,
            "subject": updated_epic.subject,
            "description": getattr(updated_epic, "description", ""),
            "status": "updated"
        }

    @handle_api_error
    def delete_epic(self, epic_id: int) -> Dict[str, str]:
        """Delete an epic.
        
        Args:
            epic_id: ID of the epic to delete
            
        Returns:
            Status dictionary
        """
        epic = self.make_api_call(self.api.epics.get, epic_id)
        self.make_api_call(epic.delete)
        
        return {"status": "deleted", "message": f"Epic {epic_id} successfully deleted"}

    # User Stories CRUD
    @handle_api_error
    def list_user_stories(self, 
                          project_id: Optional[int] = None, 
                          milestone_id: Optional[int] = None, 
                          epic_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """List user stories with optional filtering.
        
        Args:
            project_id: Optional project ID filter
            milestone_id: Optional milestone/sprint ID filter
            epic_id: Optional epic ID filter
            
        Returns:
            List of user story dictionaries
        """
        if project_id:
            stories = self.make_api_call(self.api.user_stories.list, project=project_id)
        elif milestone_id:
            stories = self.make_api_call(self.api.user_stories.list, milestone=milestone_id)
        elif epic_id:
            stories = self.make_api_call(self.api.user_stories.list, epic=epic_id)
        else:
            stories = self.make_api_call(self.api.user_stories.list)
            
        return [{
            "id": us.id,
            "ref": getattr(us, "ref", None),
            "subject": us.subject,
            "description": getattr(us, "description", ""),
            "status": getattr(us, "status", None),
            "assigned_to": getattr(us, "assigned_to", None),
            "milestone": getattr(us, "milestone", None),
            "project": getattr(us, "project", None),
            "points": getattr(us, "points", None),
            "is_blocked": getattr(us, "is_blocked", False),
            "blocked_note": getattr(us, "blocked_note", "")
        } for us in stories]

    @handle_api_error
    def get_user_story(self, user_story_id: int) -> Dict[str, Any]:
        """Get details of a specific user story.
        
        Args:
            user_story_id: ID of the user story to retrieve
            
        Returns:
            User story details dictionary
        """
        story = self.make_api_call(self.api.user_stories.get, user_story_id)
        return {
            "id": story.id,
            "ref": getattr(story, "ref", None),
            "subject": story.subject,
            "description": getattr(story, "description", ""),
            "status": getattr(story, "status", None),
            "assigned_to": getattr(story, "assigned_to", None),
            "milestone": getattr(story, "milestone", None),
            "project": getattr(story, "project", None),
            "points": getattr(story, "points", None),
            "is_blocked": getattr(story, "is_blocked", False),
            "blocked_note": getattr(story, "blocked_note", "")
        }

    @handle_api_error
    def create_user_story(self, 
                          project_id: int, 
                          subject: str, 
                          description: Optional[str] = None, 
                          milestone_id: Optional[int] = None) -> Dict[str, Any]:
        """Create a new user story in a project.
        
        Args:
            project_id: ID of the project to create the story in
            subject: User story title/subject
            description: Optional user story description
            milestone_id: Optional milestone/sprint ID to assign
            
        Returns:
            Created user story details
        """
        # Build parameters dictionary
        params = {
            "project": project_id,
            "subject": subject,
        }

        # Add optional parameters
        if description:
            params["description"] = description
        if milestone_id:
            params["milestone"] = milestone_id

        try:
            # Create the user story using the API directly
            story = self.make_api_call(self.api.user_stories.create, **params)

            # Return the result with safe attribute access
            return {
                "id": story.id,
                "subject": story.subject,
                "description": getattr(story, "description", ""),
                "milestone": getattr(story, "milestone", None),
                "status": "created"
            }
        except Exception as e:
            logger.warning(f"Error creating user story with direct API: {str(e)}")
            # Fall back to alternative approach
            project = self.make_api_call(self.api.projects.get, project_id)

            alt_params = {
                "subject": subject,
            }
            if description:
                alt_params["description"] = description
            if milestone_id:
                alt_params["milestone"] = milestone_id

            story = self.make_api_call(project.add_user_story, **alt_params)
            return {
                "id": story.id,
                "subject": story.subject,
                "description": getattr(story, "description", ""),
                "milestone": getattr(story, "milestone", None),
                "status": "created"
            }

    @handle_api_error
    def update_user_story(self, 
                          user_story_id: int, 
                          subject: Optional[str] = None, 
                          description: Optional[str] = None,
                          status_id: Optional[int] = None,
                          milestone_id: Optional[int] = None,
                          **kwargs) -> Dict[str, Any]:
        """Update an existing user story.
        
        Args:
            user_story_id: ID of the user story to update
            subject: Optional new subject
            description: Optional new description
            status_id: Optional new status ID
            milestone_id: Optional new milestone ID
            **kwargs: Additional attributes to update
            
        Returns:
            Updated user story details
        """
        # Build update params
        update_params = {}
        if subject:
            update_params["subject"] = subject
        if description:
            update_params["description"] = description
        if status_id:
            update_params["status"] = status_id
        if milestone_id:
            update_params["milestone"] = milestone_id
            
        # Add any additional parameters
        update_params.update(kwargs)
        
        story = self.make_api_call(self.api.user_stories.get, user_story_id)
        updated_story = self.make_api_call(story.update, **update_params)
        
        return {
            "id": updated_story.id,
            "subject": updated_story.subject,
            "description": getattr(updated_story, "description", ""),
            "status": getattr(updated_story, "status", None),
            "milestone": getattr(updated_story, "milestone", None),
            "updated_status": "success"
        }

    @handle_api_error
    def delete_user_story(self, user_story_id: int) -> Dict[str, str]:
        """Delete a user story.
        
        Args:
            user_story_id: ID of the user story to delete
            
        Returns:
            Status dictionary
        """
        story = self.make_api_call(self.api.user_stories.get, user_story_id)
        self.make_api_call(story.delete)
        
        return {"status": "deleted", "message": f"User story {user_story_id} successfully deleted"}

    # Tasks CRUD
    def list_tasks(self, project_id=None, user_story_id=None):
        if project_id:
            tasks = self.api.tasks.list(project=project_id)
        elif user_story_id:
            tasks = self.api.tasks.list(user_story=user_story_id)
        else:
            tasks = self.api.tasks.list()
        return [{
            "id": t.id,
            "subject": t.subject,
            "description": getattr(t, "description", ""),
            "status": getattr(t, "status", None),
            "assigned_to": getattr(t, "assigned_to", None),
            "user_story": getattr(t, "user_story", None)
        } for t in tasks]

    def get_task(self, task_id):
        task = self.api.tasks.get(task_id)
        return {"id": task.id, "subject": task.subject, "description": task.description}

    def create_task(self, user_story_id, subject, description=None, status_id=None):
        try:
            # First approach: Try to get the user story and add a task to it
            story = self.api.user_stories.get(user_story_id)

            params = {"subject": subject}
            if description:
                params["description"] = description
            if status_id:
                params["status"] = status_id

            task = story.add_task(**params)

            return {
                "id": task.id,
                "subject": task.subject,
                "description": getattr(task, "description", ""),
                "user_story": user_story_id
            }
        except Exception as e:
            print(f"Error creating task via user story: {str(e)}")

            # Alternative approach: Create task directly
            params = {
                "subject": subject,
                "user_story": user_story_id
            }

            if description:
                params["description"] = description
            if status_id:
                params["status"] = status_id

            task = self.api.tasks.create(**params)

            return {
                "id": task.id,
                "subject": task.subject,
                "description": getattr(task, "description", ""),
                "user_story": getattr(task, "user_story", user_story_id)
            }

    def update_task(self, task_id, **kwargs):
        task = self.api.tasks.get(task_id)
        task = task.update(**kwargs)
        return {"id": task.id, "subject": task.subject, "description": task.description}

    def delete_task(self, task_id):
        task = self.api.tasks.get(task_id)
        task.delete()
        return {"status": "deleted"}

    # Issues CRUD
    def list_issues(self, project_id=None):
        if project_id:
            project = self.api.projects.get(project_id)
            issues = project.list_issues()
        else:
            issues = self.api.issues.list()
        return [{"id": i.id, "subject": i.subject, "description": i.description} for i in issues]

    def get_issue(self, issue_id):
        issue = self.api.issues.get(issue_id)
        return {"id": issue.id, "subject": issue.subject, "description": issue.description}

    def create_issue(self, project_id, subject, description=None, priority_id=None, status_id=None, type_id=None, severity_id=None):
        try:
            # First approach: Try to create issue through project
            project = self.api.projects.get(project_id)

            params = {
                "subject": subject
            }

            if description:
                params["description"] = description
            if priority_id:
                params["priority"] = priority_id
            if status_id:
                params["status"] = status_id
            if type_id:
                params["type"] = type_id
            if severity_id:
                params["severity"] = severity_id

            issue = project.add_issue(**params)

            return {
                "id": issue.id,
                "subject": issue.subject,
                "description": getattr(issue, "description", ""),
                "priority": getattr(issue, "priority", None),
                "status": getattr(issue, "status", None),
                "type": getattr(issue, "type", None),
                "severity": getattr(issue, "severity", None)
            }
        except Exception as e:
            print(f"Error creating issue via project: {str(e)}")

            # Alternative approach: Create issue directly
            params = {
                "project": project_id,
                "subject": subject
            }

            if description:
                params["description"] = description
            if priority_id:
                params["priority"] = priority_id
            if status_id:
                params["status"] = status_id
            if type_id:
                params["type"] = type_id
            if severity_id:
                params["severity"] = severity_id

            issue = self.api.issues.create(**params)

            return {
                "id": issue.id,
                "subject": issue.subject,
                "description": getattr(issue, "description", ""),
                "priority": getattr(issue, "priority", None),
                "status": getattr(issue, "status", None),
                "type": getattr(issue, "type", None),
                "severity": getattr(issue, "severity", None)
            }

    def update_issue(self, issue_id, **kwargs):
        issue = self.api.issues.get(issue_id)
        issue = issue.update(**kwargs)
        return {"id": issue.id, "subject": issue.subject, "description": issue.description}

    def delete_issue(self, issue_id):
        issue = self.api.issues.get(issue_id)
        issue.delete()
        return {"status": "deleted"}

    # Sprints (Milestones) CRUD
    def list_sprints(self, project_id=None):
        if project_id:
            project = self.api.projects.get(project_id)
            sprints = project.list_milestones()
        else:
            sprints = self.api.milestones.list()
        return [{
            "id": s.id,
            "name": s.name,
            "estimated_start": s.estimated_start,
            "estimated_finish": s.estimated_finish
        } for s in sprints]

    def get_sprint(self, sprint_id):
        sprint = self.api.milestones.get(sprint_id)
        return {
            "id": sprint.id,
            "name": sprint.name,
            "start_date": sprint.estimated_start,
            "end_date": sprint.estimated_finish,
            "project": sprint.project
        }

    def create_sprint(self, project_id, name, start_date, end_date):
        project = self.api.projects.get(project_id)
        sprint = project.add_milestone(
            name=name,
            estimated_start=start_date,
            estimated_finish=end_date
        )
        return {
            "id": sprint.id,
            "name": sprint.name,
            "estimated_start": sprint.estimated_start,
            "estimated_finish": sprint.estimated_finish
        }

    def update_sprint(self, sprint_id, **kwargs):
        sprint = self.api.milestones.get(sprint_id)
        sprint = sprint.update(**kwargs)
        return {
            "id": sprint.id,
            "name": sprint.name,
            "start_date": sprint.estimated_start,
            "end_date": sprint.estimated_finish
        }

    def delete_sprint(self, sprint_id):
        sprint = self.api.milestones.get(sprint_id)
        sprint.delete()
        return {"status": "deleted"}

    # Status Types
    def list_task_statuses(self, project_id):
        """List all available task statuses for a project"""
        project = self.api.projects.get(project_id)
        return [{
            "id": status.id,
            "name": status.name,
            "color": status.color,
            "is_closed": status.is_closed
        } for status in project.task_statuses]

    def list_epic_statuses(self, project_id):
        """List all available epic statuses for a project"""
        project = self.api.projects.get(project_id)
        return [{
            "id": status.id,
            "name": status.name,
            "color": status.color,
            "is_closed": status.is_closed
        } for status in project.epic_statuses]

    def list_user_story_statuses(self, project_id):
        """List all available user story statuses for a project"""
        project = self.api.projects.get(project_id)
        return [{
            "id": status.id,
            "name": status.name,
            "color": status.color,
            "is_closed": status.is_closed
        } for status in project.user_story_statuses]

    def list_issue_statuses(self, project_id):
        """List all available issue statuses for a project"""
        project = self.api.projects.get(project_id)
        return [{
            "id": status.id,
            "name": status.name,
            "color": status.color,
            "is_closed": status.is_closed
        } for status in project.issue_statuses]

    def list_issue_types(self, project_id):
        """List all available issue types for a project"""
        project = self.api.projects.get(project_id)
        return [{
            "id": type.id,
            "name": type.name,
            "color": type.color
        } for type in project.issue_types]

    def list_issue_priorities(self, project_id):
        """List all available issue priorities for a project"""
        project = self.api.projects.get(project_id)
        return [{
            "id": priority.id,
            "name": priority.name,
            "color": priority.color
        } for priority in project.priorities]

    def list_issue_severities(self, project_id):
        """List all available issue severities for a project"""
        project = self.api.projects.get(project_id)
        return [{
            "id": severity.id,
            "name": severity.name,
            "color": severity.color
        } for severity in project.severities]

    # User Management
    def list_project_members(self, project_id):
        """List all members of a project"""
        project = self.api.projects.get(project_id)
        return [{
            "id": member.id,
            "username": member.username,
            "full_name": getattr(member, "full_name", ""),
            "email": getattr(member, "email", ""),
            "role": getattr(member, "role_name", "")
        } for member in project.members]

    def invite_user(self, project_id, email, role_id):
        """Invite a user to join a project with a specific role"""
        # Get the project first
        project = self.api.projects.get(project_id)
        # Extract username from email for required field
        username = email.split('@')[0]

        # Use project method to add member
        invitation = project.add_membership(
            email=email,
            role=role_id,
            username=username
        )

        return {
            "email": getattr(invitation, "email", email),
            "role_id": getattr(invitation, "role", role_id),
            "status": "invited",
            "message": f"Invitation sent to {email}"
        }

    def list_project_roles(self, project_id):
        """List all available roles in a project"""
        project = self.api.projects.get(project_id)
        return [{
            "id": role.id,
            "name": role.name,
            "permissions": role.permissions
        } for role in project.list_roles()]

    # Assignment Functions
    def assign_epic(self, epic_id, user_id):
        """Assign an epic to a user"""
        epic = self.api.epics.get(epic_id)
        epic = epic.update(assigned_to=user_id)
        return {
            "epic_id": epic.id,
            "assigned_to": epic.assigned_to,
            "status": "assigned"
        }

    def assign_user_story(self, user_story_id, user_id):
        """Assign a user story to a user"""
        story = self.api.user_stories.get(user_story_id)
        story = story.update(assigned_to=user_id)
        return {
            "user_story_id": story.id,
            "assigned_to": story.assigned_to,
            "status": "assigned"
        }

    def assign_task(self, task_id, user_id):
        """Assign a task to a user"""
        task = self.api.tasks.get(task_id)
        task = task.update(assigned_to=user_id)
        return {
            "task_id": task.id,
            "assigned_to": task.assigned_to,
            "status": "assigned"
        }

    def assign_issue(self, issue_id, user_id):
        """Assign an issue to a user"""
        issue = self.api.issues.get(issue_id)
        issue = issue.update(assigned_to=user_id)
        return {
            "issue_id": issue.id,
            "assigned_to": issue.assigned_to,
            "status": "assigned"
        }

    # Roles CRUD
    def list_roles(self, project_id=None):
        """List all roles, optionally filtered by project"""
        if project_id:
            project = self.api.projects.get(project_id)
            roles = project.list_roles()
        else:
            roles = self.api.roles.list()
        return [{
            "id": role.id,
            "name": role.name,
            "permissions": role.permissions
        } for role in roles]

    def get_role(self, role_id):
        """Get a specific role by ID"""
        role = self.api.roles.get(role_id)
        return {
            "id": role.id,
            "name": role.name,
            "permissions": role.permissions
        }

    def create_role(self, project_id, name, permissions=None):
        """Create a new role in a project"""
        project = self.api.projects.get(project_id)
        role = project.add_role(name=name, permissions=permissions or [])
        return {
            "id": role.id,
            "name": role.name,
            "permissions": role.permissions
        }

    def update_role(self, role_id, **kwargs):
        """Update an existing role"""
        role = self.api.roles.get(role_id)
        role = role.update(**kwargs)
        return {
            "id": role.id,
            "name": role.name,
            "permissions": role.permissions
        }

    def delete_role(self, role_id):
        """Delete a role"""
        role = self.api.roles.get(role_id)
        role.delete()
        return {"status": "deleted"}

    def get_role_permissions(self, role_id):
        """Get permissions for a specific role"""
        role = self.api.roles.get(role_id)
        return {
            "role_id": role.id,
            "permissions": role.permissions
        }

    def update_role_permissions(self, role_id, permissions):
        """Update permissions for a specific role"""
        role = self.api.roles.get(role_id)
        role = role.update(permissions=permissions)
        return {
            "role_id": role.id,
            "permissions": role.permissions
        }
