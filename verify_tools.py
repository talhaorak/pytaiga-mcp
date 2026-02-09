#!/usr/bin/env python
"""
Comprehensive verification script for Taiga MCP tools.
Tests the full lifecycle (Create-Read-Update-Delete) of major resources.
"""

import json
import os
import time
import uuid
import logging
from src.config import settings
from src.server import (
    login,
    list_projects,
    get_project,
    # User Stories
    create_user_story,
    get_user_story,
    update_user_story,
    delete_user_story,
    # Tasks
    create_task,
    get_task,
    update_task,
    delete_task,
    # Epics
    create_epic,
    get_epic,
    update_epic,
    delete_epic,
    link_user_story_to_epic,
    # Issues
    create_issue,
    get_issue,
    update_issue,
    delete_issue,
    get_issue_statuses,
    get_issue_priorities,
    get_issue_severities,
    get_issue_types,
    # Milestones/Wiki
    list_milestones,
    list_wiki_pages,
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Config
TEST_HOST = os.environ.get("TAIGA_TEST_HOST", settings.host)
TEST_USERNAME = os.environ.get("TAIGA_TEST_USERNAME", settings.get_username_value())
TEST_PASSWORD = os.environ.get("TAIGA_TEST_PASSWORD", settings.get_password_value())


def run_verification():
    print(f"Starting verification on {TEST_HOST}...")

    # 1. Login
    try:
        login_res = login(TEST_HOST, TEST_USERNAME, TEST_PASSWORD)
        session_id = login_res["session_id"]
        print("✅ Login successful")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return

    # 2. Get Project
    try:
        projects = list_projects(session_id=session_id)
        if not projects:
            print("❌ No projects found. Cannot proceed.")
            return
        
        # Prefer Project ID 10 (known working), otherwise avoid corrupted ID 9
        # Fallback to first available if 10 not found and others are valid
        project = next((p for p in projects if p["id"] == 10), None)
        if not project:
             project = next((p for p in projects if p["id"] != 9), projects[0])
             
        pid = project["id"]
        print(f"✅ Found project: {project['name']} (ID: {pid})")
    except Exception as e:
        print(f"❌ Project retrieval failed: {e}")
        return

    # 3. User Story Lifecycle
    print("\n--- Testing User Story ---")
    try:
        us_subject = f"Verify Story {uuid.uuid4()}"
        us = create_user_story(pid, us_subject, session_id=session_id)
        print(f"✅ Created Story (ID: {us['id']})")

        us_get = get_user_story(us["id"], session_id=session_id)
        assert us_get["subject"] == us_subject
        print("✅ Retrieved Story")

        update_user_story(
            us["id"], kwargs='{"subject": "Updated Story Name"}', session_id=session_id
        )
        print("✅ Updated Story")

        delete_user_story(us["id"], session_id=session_id)
        print("✅ Deleted Story")
    except Exception as e:
        print(f"❌ User Story failed: {e}")

    # 4. Task Lifecycle
    print("\n--- Testing Task ---")
    try:
        task_subject = f"Verify Task {uuid.uuid4()}"
        task = create_task(pid, task_subject, session_id=session_id)
        print(f"✅ Created Task (ID: {task['id']})")

        task_get = get_task(task["id"], session_id=session_id)
        assert task_get["subject"] == task_subject
        print("✅ Retrieved Task")

        update_task(task["id"], kwargs='{"subject": "Updated Task Name"}', session_id=session_id)
        print("✅ Updated Task")

        delete_task(task["id"], session_id=session_id)
        print("✅ Deleted Task")
    except Exception as e:
        print(f"❌ Task failed: {e}")

    # 5. Epic Lifecycle
    print("\n--- Testing Epic ---")
    try:
        epic_subject = f"Verify Epic {uuid.uuid4()}"
        epic = create_epic(pid, epic_subject, session_id=session_id)
        print(f"✅ Created Epic (ID: {epic['id']})")

        epic_get = get_epic(epic["id"], session_id=session_id)
        assert epic_get["subject"] == epic_subject
        print("✅ Retrieved Epic")

        update_epic(epic["id"], kwargs='{"subject": "Updated Epic Name"}', session_id=session_id)
        print("✅ Updated Epic")

        delete_epic(epic["id"], session_id=session_id)
        print("✅ Deleted Epic")
    except Exception as e:
        print(f"❌ Epic failed: {e}")

    # 6. Issue Lifecycle (Complex)
    print("\n--- Testing Issue ---")
    try:
        # Fetch required metadata
        priorities = get_issue_priorities(pid, session_id=session_id)
        statuses = get_issue_statuses(pid, session_id=session_id)
        severities = get_issue_severities(pid, session_id=session_id)
        types = get_issue_types(pid, session_id=session_id)

        if priorities and statuses and severities and types:
            issue_subject = f"Verify Issue {uuid.uuid4()}"
            issue = create_issue(
                pid,
                issue_subject,
                priority_id=priorities[0]["id"],
                status_id=statuses[0]["id"],
                severity_id=severities[0]["id"],
                type_id=types[0]["id"],
                session_id=session_id,
            )
            print(f"✅ Created Issue (ID: {issue['id']})")

            update_issue(
                issue["id"], kwargs='{"subject": "Updated Issue Name"}', session_id=session_id
            )
            print("✅ Updated Issue")

            delete_issue(issue["id"], session_id=session_id)
            print("✅ Deleted Issue")
        else:
            print("⚠️ Skipping Issue creation (metadata missing)")
    except Exception as e:
        print(f"❌ Issue failed: {e}")

    # 7. Lists
    print("\n--- Testing Lists ---")
    try:
        milestones = list_milestones(pid, session_id=session_id)
        print(f"✅ Listed Milestones: {len(milestones)}")

        wiki = list_wiki_pages(pid, session_id=session_id)
        print(f"✅ Listed Wiki Pages: {len(wiki)}")
    except Exception as e:
        print(f"❌ Lists failed: {e}")

    # 8. Linking
    print("\n--- Testing Linking ---")
    try:
        # Create temp story and epic
        link_story = create_user_story(
            pid, f"Verify Link Story {uuid.uuid4()}", session_id=session_id
        )
        link_epic = create_epic(pid, f"Verify Link Epic {uuid.uuid4()}", session_id=session_id)

        # Link them
        print(f"Linking Story {link_story['id']} to Epic {link_epic['id']}...")
        link_res = link_user_story_to_epic(link_epic["id"], link_story["id"], session_id=session_id)
        print(f"✅ Linked: {link_res}")

        # Cleanup
        delete_user_story(link_story["id"], session_id=session_id)
        delete_epic(link_epic["id"], session_id=session_id)
        print("✅ Cleanup successful")
    except Exception as e:
        print(f"❌ Linking failed: {e}")

    print("\nVerification Complete.")


if __name__ == "__main__":
    run_verification()
