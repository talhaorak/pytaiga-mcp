#!/usr/bin/env python
"""
Manual debugging script for integration tests.
Run with: python debug_integration.py
"""
import json
import uuid
import time

# Import the server module
from src.server import login, list_projects, update_project, get_project
from src.server import list_user_stories, create_user_story

# Configure test parameters
TEST_HOST = "http://localhost:9000"
TEST_USERNAME = "test"
TEST_PASSWORD = "test"


def print_json(label, data):
    """Helper to print JSON data with indentation"""
    print(f"\n===== {label} =====")
    print(json.dumps(data, indent=2))
    print("=" * (len(label) + 12))


# Main debug function
def debug_integration():
    print(f"Starting debug session for Taiga at {TEST_HOST}")
    
    # 1. Login and get session
    try:
        print(f"Logging in as {TEST_USERNAME}...")
        result = login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)
        session_id = result["session_id"]
        print(f"Login successful! Session ID: {session_id}")
    except Exception as e:
        print(f"LOGIN ERROR: {e}")
        return
    
    # 2. List projects
    try:
        print("\nListing projects...")
        projects = list_projects(session_id)
        print(f"Found {len(projects)} projects")
        
        if len(projects) == 0:
            print("No projects available - cannot continue testing")
            return
        
        # Print first project details
        print_json("First Project", projects[0])
        project_id = projects[0]["id"]
    except Exception as e:
        print(f"PROJECT LIST ERROR: {e}")
        return
    
    # 3. Get specific project details
    try:
        print(f"\nGetting details for project ID {project_id}...")
        project = get_project(session_id, project_id)
        print_json("Project Details", project)
    except Exception as e:
        print(f"PROJECT DETAILS ERROR: {e}")
    
    # 4. Create and verify user story
    try:
        subject = f"Debug Story {uuid.uuid4()}"
        print(f"\nCreating user story '{subject}' in project {project_id}...")
        
        story = create_user_story(session_id, project_id, subject, 
                                description="Created by debug script")
        story_id = story["id"]
        print_json("Created Story", story)
        
        print("\nListing user stories to verify creation...")
        time.sleep(1)  # Small delay to ensure creation is complete
        stories = list_user_stories(session_id, project_id)
        print(f"Found {len(stories)} stories")
        
        # Find our story
        found = False
        for s in stories:
            if s["id"] == story_id:
                found = True
                print_json("Our Story in List", s)
                break
        
        if not found:
            print(f"WARNING: Created story (ID: {story_id}) not found in stories list!")
    except Exception as e:
        print(f"USER STORY ERROR: {e}")


if __name__ == "__main__":
    debug_integration()
