import pytest
from src.taiga_client import ProjectCreate


class TestProjects:
    """Tests for project-related operations."""
    
    def test_list_projects(self, authenticated_client, mock_project):
        """Test listing projects."""
        # Arrange
        client, _ = authenticated_client
        mock_project2 = type('Project', (), {'id': 2, 'name': 'Project 2'})
        client.api.projects.list.return_value = [mock_project, mock_project2]
        
        # Act
        result = client.list_projects()
        
        # Assert
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["name"] == "Test Project"
        assert result[1]["id"] == 2
        assert result[1]["name"] == "Project 2"
        client.api.projects.list.assert_called_once()

    def test_get_project(self, authenticated_client, mock_project):
        """Test getting a specific project."""
        # Arrange
        client, _ = authenticated_client
        client.api.projects.get.return_value = mock_project
        
        # Act
        result = client.get_project(1)
        
        # Assert
        assert result["id"] == 1
        assert result["name"] == "Test Project"
        assert result["description"] == "Test Description"
        client.api.projects.get.assert_called_once_with(1)

    def test_create_project_with_model(self, authenticated_client, mock_project):
        """Test creating a project using Pydantic model."""
        # Arrange
        client, _ = authenticated_client
        client.api.projects.create.return_value = mock_project
        
        project_data = ProjectCreate(
            name="Test Project",
            description="Test Description"
        )
        
        # Act
        result = client.create_project(project_data)
        
        # Assert
        assert result["id"] == 1
        assert result["name"] == "Test Project"
        assert result["description"] == "Test Description"
        assert result["status"] == "created"
        
        client.api.projects.create.assert_called_with(
            name="Test Project",
            description="Test Description"
        )

    def test_create_project_with_dict(self, authenticated_client, mock_project):
        """Test creating a project using dictionary."""
        # Arrange
        client, _ = authenticated_client
        client.api.projects.create.return_value = mock_project
        
        project_data = {
            "name": "Test Project",
            "description": "Test Description"
        }
        
        # Act
        result = client.create_project(project_data)
        
        # Assert
        assert result["id"] == 1
        assert result["name"] == "Test Project"
        assert result["description"] == "Test Description"
        assert result["status"] == "created"
        
        client.api.projects.create.assert_called_with(
            name="Test Project",
            description="Test Description"
        )

    def test_update_project(self, authenticated_client, mock_project):
        """Test updating a project."""
        # Arrange
        client, _ = authenticated_client
        client.api.projects.get.return_value = mock_project
        
        updated_project = type('Project', (), {
            'id': 1, 
            'name': 'Updated Project', 
            'description': 'Updated Description'
        })
        mock_project.update.return_value = updated_project
        
        # Act
        result = client.update_project(1, name="Updated Project", description="Updated Description")
        
        # Assert
        assert result["id"] == 1
        assert result["name"] == "Updated Project"
        assert result["description"] == "Updated Description"
        assert result["status"] == "updated"
        
        client.api.projects.get.assert_called_once_with(1)
        mock_project.update.assert_called_once_with(
            name="Updated Project", 
            description="Updated Description"
        )

    def test_delete_project(self, authenticated_client, mock_project):
        """Test deleting a project."""
        # Arrange
        client, _ = authenticated_client
        client.api.projects.get.return_value = mock_project
        
        # Act
        result = client.delete_project(1)
        
        # Assert
        assert result["status"] == "deleted"
        assert f"Project 1 successfully deleted" in result["message"]
        
        client.api.projects.get.assert_called_once_with(1)
        mock_project.delete.assert_called_once() 