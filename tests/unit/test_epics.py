import pytest
from unittest.mock import Mock


class TestEpics:
    """Tests for epic-related operations."""
    
    def test_list_epics_all(self, authenticated_client, mock_epic):
        """Test listing all epics."""
        # Arrange
        client, _ = authenticated_client
        mock_epic2 = Mock()
        mock_epic2.id = 2
        mock_epic2.subject = "Epic 2"
        mock_epic2.description = "Description 2"
        
        client.api.epics.list.return_value = [mock_epic, mock_epic2]
        
        # Act
        result = client.list_epics()
        
        # Assert
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["subject"] == "Test Epic"
        assert result[1]["id"] == 2
        assert result[1]["subject"] == "Epic 2"
        client.api.epics.list.assert_called_once()

    def test_list_epics_by_project(self, authenticated_client, mock_epic, mock_project):
        """Test listing epics filtered by project."""
        # Arrange
        client, _ = authenticated_client
        mock_project.list_epics.return_value = [mock_epic]
        client.api.projects.get.return_value = mock_project
        
        # Act
        result = client.list_epics(project_id=1)
        
        # Assert
        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["subject"] == "Test Epic"
        client.api.projects.get.assert_called_once_with(1)
        mock_project.list_epics.assert_called_once()

    def test_get_epic(self, authenticated_client, mock_epic):
        """Test getting a specific epic."""
        # Arrange
        client, _ = authenticated_client
        client.api.epics.get.return_value = mock_epic
        
        # Act
        result = client.get_epic(1)
        
        # Assert
        assert result["id"] == 1
        assert result["subject"] == "Test Epic"
        assert result["description"] == "Test Epic Description"
        client.api.epics.get.assert_called_once_with(1)

    def test_create_epic(self, authenticated_client, mock_epic, mock_project):
        """Test creating an epic."""
        # Arrange
        client, _ = authenticated_client
        client.api.projects.get.return_value = mock_project
        mock_project.add_epic.return_value = mock_epic
        
        # Act
        result = client.create_epic(
            project_id=1,
            subject="Test Epic",
            description="Test Epic Description"
        )
        
        # Assert
        assert result["id"] == 1
        assert result["subject"] == "Test Epic"
        assert result["description"] == "Test Epic Description"
        assert result["status"] == "created"
        
        client.api.projects.get.assert_called_once_with(1)
        mock_project.add_epic.assert_called_once_with(
            subject="Test Epic",
            description="Test Epic Description"
        )

    def test_update_epic(self, authenticated_client, mock_epic):
        """Test updating an epic."""
        # Arrange
        client, _ = authenticated_client
        client.api.epics.get.return_value = mock_epic
        
        updated_epic = Mock()
        updated_epic.id = 1
        updated_epic.subject = "Updated Epic"
        updated_epic.description = "Updated Description"
        
        mock_epic.update.return_value = updated_epic
        
        # Act
        result = client.update_epic(
            epic_id=1,
            subject="Updated Epic",
            description="Updated Description"
        )
        
        # Assert
        assert result["id"] == 1
        assert result["subject"] == "Updated Epic"
        assert result["description"] == "Updated Description"
        assert result["status"] == "updated"
        
        client.api.epics.get.assert_called_once_with(1)
        mock_epic.update.assert_called_once_with(
            subject="Updated Epic",
            description="Updated Description"
        )

    def test_delete_epic(self, authenticated_client, mock_epic):
        """Test deleting an epic."""
        # Arrange
        client, _ = authenticated_client
        client.api.epics.get.return_value = mock_epic
        
        # Act
        result = client.delete_epic(1)
        
        # Assert
        assert result["status"] == "deleted"
        assert "Epic 1 successfully deleted" in result["message"]
        
        client.api.epics.get.assert_called_once_with(1)
        mock_epic.delete.assert_called_once() 