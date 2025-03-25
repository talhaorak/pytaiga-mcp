import pytest
from unittest.mock import Mock
from src.taiga_client import UserStoryCreate


class TestUserStories:
    """Tests for user story-related operations."""
    
    def test_list_user_stories_all(self, authenticated_client, mock_user_story):
        """Test listing all user stories."""
        # Arrange
        client, _ = authenticated_client
        mock_user_story2 = Mock()
        mock_user_story2.id = 2
        mock_user_story2.subject = "User Story 2"
        mock_user_story2.description = "Description 2"
        
        client.api.user_stories.list.return_value = [mock_user_story, mock_user_story2]
        
        # Act
        result = client.list_user_stories()
        
        # Assert
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["subject"] == "Test User Story"
        assert result[1]["id"] == 2
        assert result[1]["subject"] == "User Story 2"
        client.api.user_stories.list.assert_called_once()

    def test_list_user_stories_by_project(self, authenticated_client, mock_user_story):
        """Test listing user stories filtered by project."""
        # Arrange
        client, _ = authenticated_client
        client.api.user_stories.list.return_value = [mock_user_story]
        
        # Act
        result = client.list_user_stories(project_id=1)
        
        # Assert
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["subject"] == "Test User Story"
        client.api.user_stories.list.assert_called_once_with(project=1)

    def test_list_user_stories_by_milestone(self, authenticated_client, mock_user_story):
        """Test listing user stories filtered by milestone."""
        # Arrange
        client, _ = authenticated_client
        client.api.user_stories.list.return_value = [mock_user_story]
        
        # Act
        result = client.list_user_stories(milestone_id=1)
        
        # Assert
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["subject"] == "Test User Story"
        client.api.user_stories.list.assert_called_once_with(milestone=1)

    def test_list_user_stories_by_epic(self, authenticated_client, mock_user_story):
        """Test listing user stories filtered by epic."""
        # Arrange
        client, _ = authenticated_client
        client.api.user_stories.list.return_value = [mock_user_story]
        
        # Act
        result = client.list_user_stories(epic_id=1)
        
        # Assert
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["subject"] == "Test User Story"
        client.api.user_stories.list.assert_called_once_with(epic=1)

    def test_get_user_story(self, authenticated_client, mock_user_story):
        """Test getting a specific user story."""
        # Arrange
        client, _ = authenticated_client
        client.api.user_stories.get.return_value = mock_user_story
        
        # Act
        result = client.get_user_story(1)
        
        # Assert
        assert result["id"] == 1
        assert result["subject"] == "Test User Story"
        assert result["description"] == "Test User Story Description"
        client.api.user_stories.get.assert_called_once_with(1)

    def test_create_user_story_direct_api(self, authenticated_client, mock_user_story):
        """Test creating a user story using direct API."""
        # Arrange
        client, _ = authenticated_client
        client.api.user_stories.create.return_value = mock_user_story
        
        # Act
        result = client.create_user_story(
            project_id=1,
            subject="Test User Story",
            description="Test User Story Description",
            milestone_id=2
        )
        
        # Assert
        assert result["id"] == 1
        assert result["subject"] == "Test User Story"
        assert result["description"] == "Test User Story Description"
        assert result["status"] == "created"
        
        client.api.user_stories.create.assert_called_once_with(
            project=1,
            subject="Test User Story",
            description="Test User Story Description",
            milestone=2
        )

    def test_create_user_story_fallback(self, authenticated_client, mock_user_story, mock_project):
        """Test creating a user story using fallback method."""
        # Arrange
        client, _ = authenticated_client
        # Make direct API fail
        client.api.user_stories.create.side_effect = Exception("API Error")
        client.api.projects.get.return_value = mock_project
        mock_project.add_user_story.return_value = mock_user_story
        
        # Act
        result = client.create_user_story(
            project_id=1,
            subject="Test User Story",
            description="Test User Story Description",
            milestone_id=2
        )
        
        # Assert
        assert result["id"] == 1
        assert result["subject"] == "Test User Story"
        assert result["description"] == "Test User Story Description"
        assert result["status"] == "created"
        
        client.api.projects.get.assert_called_once_with(1)
        mock_project.add_user_story.assert_called_once_with(
            subject="Test User Story",
            description="Test User Story Description",
            milestone=2
        )

    def test_update_user_story(self, authenticated_client, mock_user_story):
        """Test updating a user story."""
        # Arrange
        client, _ = authenticated_client
        client.api.user_stories.get.return_value = mock_user_story
        
        updated_user_story = Mock()
        updated_user_story.id = 1
        updated_user_story.subject = "Updated User Story"
        updated_user_story.description = "Updated Description"
        updated_user_story.status = 2
        updated_user_story.milestone = 3
        
        mock_user_story.update.return_value = updated_user_story
        
        # Act
        result = client.update_user_story(
            user_story_id=1,
            subject="Updated User Story",
            description="Updated Description",
            status_id=2,
            milestone_id=3
        )
        
        # Assert
        assert result["id"] == 1
        assert result["subject"] == "Updated User Story"
        assert result["description"] == "Updated Description"
        assert result["status"] == 2
        assert result["milestone"] == 3
        assert result["updated_status"] == "success"
        
        client.api.user_stories.get.assert_called_once_with(1)
        mock_user_story.update.assert_called_once_with(
            subject="Updated User Story",
            description="Updated Description",
            status=2,
            milestone=3
        )

    def test_delete_user_story(self, authenticated_client, mock_user_story):
        """Test deleting a user story."""
        # Arrange
        client, _ = authenticated_client
        client.api.user_stories.get.return_value = mock_user_story
        
        # Act
        result = client.delete_user_story(1)
        
        # Assert
        assert result["status"] == "deleted"
        assert "User story 1 successfully deleted" in result["message"]
        
        client.api.user_stories.get.assert_called_once_with(1)
        mock_user_story.delete.assert_called_once() 