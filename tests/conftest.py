import pytest
import uuid
import time
from unittest.mock import patch, Mock
from src.taiga_client import TaigaClient, active_sessions
from src.config import Settings


@pytest.fixture(autouse=True)
def clear_active_sessions():
    """Automatically clear active sessions before and after each test."""
    active_sessions.clear()
    yield
    active_sessions.clear()


@pytest.fixture
def mock_uuid():
    """Mock uuid.uuid4 to return a predictable value."""
    fixed_uuid = uuid.UUID("12345678123456781234567812345678")
    with patch('uuid.uuid4', return_value=fixed_uuid) as mock:
        yield mock


@pytest.fixture
def mock_time():
    """Mock time.time to return a predictable value."""
    fixed_time = 1000.0
    with patch('time.time', return_value=fixed_time) as mock:
        yield mock


@pytest.fixture
def mock_settings():
    """Create a mocked Settings instance with test values."""
    with patch('src.taiga_client.Settings') as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.TAIGA_API_URL = "http://example.com"
        mock_settings.SESSION_EXPIRY = 28800  # 8 hours
        mock_settings.REQUEST_TIMEOUT = 30
        mock_settings.MAX_CONNECTIONS = 10
        mock_settings.MAX_KEEPALIVE_CONNECTIONS = 5
        mock_settings.RATE_LIMIT_REQUESTS = 100
        yield mock_settings


@pytest.fixture
def mock_taiga_api():
    """Mock the TaigaAPI class."""
    with patch('taiga.TaigaAPI') as mock:
        mock_api = mock.return_value
        yield mock_api


@pytest.fixture
def mock_httpx_client():
    """Mock the httpx.Client class."""
    with patch('httpx.Client') as mock:
        yield mock


@pytest.fixture
def taiga_client(mock_settings, mock_httpx_client):
    """Create a TaigaClient instance with mocked dependencies."""
    client = TaigaClient()
    return client


@pytest.fixture
def authenticated_client(taiga_client, mock_taiga_api, mock_uuid, mock_time):
    """Create an authenticated TaigaClient instance."""
    mock_taiga_api.auth.return_value = None  # No exception means success
    taiga_client.api = mock_taiga_api
    
    # Add to active sessions
    session_id = str(uuid.uuid4())
    active_sessions[session_id] = {
        "client": taiga_client,
        "created_at": time.time()
    }
    
    return taiga_client, session_id


@pytest.fixture
def mock_project():
    """Create a mock project object."""
    project = Mock()
    project.id = 1
    project.name = "Test Project"
    project.description = "Test Description"
    return project


@pytest.fixture
def mock_epic():
    """Create a mock epic object."""
    epic = Mock()
    epic.id = 1
    epic.subject = "Test Epic"
    epic.description = "Test Epic Description"
    return epic


@pytest.fixture
def mock_user_story():
    """Create a mock user story object."""
    story = Mock()
    story.id = 1
    story.ref = 101
    story.subject = "Test User Story"
    story.description = "Test User Story Description"
    story.status = None
    story.assigned_to = None
    story.milestone = None
    return story 