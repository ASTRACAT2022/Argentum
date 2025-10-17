import sqlite3
import logging
from typing import List, Dict, Any, Optional

# --- Configuration ---
DB_FILE = "agent_memory.db"
logger = logging.getLogger(__name__)

# --- Database Initialization ---

def initialize_database():
    """Initializes the database and creates tables if they don't exist."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            # Project table: Stores high-level goals
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Task table: Stores individual tasks within a project, including their history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    plan TEXT,
                    execution_log TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects (id)
                )
            """)
            conn.commit()
            logger.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"Database error during initialization: {e}")
        raise

# --- Project Management ---

def create_project(name: str) -> Optional[int]:
    """Creates a new project and returns its ID."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO projects (name) VALUES (?)", (name,))
            conn.commit()
            project_id = cursor.lastrowid
            logger.info(f"Created project '{name}' with ID {project_id}.")
            return project_id
    except sqlite3.IntegrityError:
        logger.warning(f"Project with name '{name}' already exists.")
        return None
    except sqlite3.Error as e:
        logger.error(f"Failed to create project '{name}': {e}")
        return None

def list_projects() -> List[Dict[str, Any]]:
    """Lists all projects."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, created_at FROM projects ORDER BY created_at DESC")
            projects = [dict(row) for row in cursor.fetchall()]
            return projects
    except sqlite3.Error as e:
        logger.error(f"Failed to list projects: {e}")
        return []

# --- Task Management ---

def create_task(project_id: int, description: str, plan: str) -> Optional[int]:
    """Creates a new task within a project and returns its ID."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tasks (project_id, description, plan) VALUES (?, ?, ?)",
                (project_id, description, plan)
            )
            conn.commit()
            task_id = cursor.lastrowid
            logger.info(f"Created task for project {project_id} with ID {task_id}.")
            return task_id
    except sqlite3.Error as e:
        logger.error(f"Failed to create task for project {project_id}: {e}")
        return None

def get_project_history(project_id: int) -> List[Dict[str, Any]]:
    """Retrieves the history of all completed tasks for a given project."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT description, plan, execution_log, status
                FROM tasks
                WHERE project_id = ? AND status = 'completed'
                ORDER BY created_at ASC
            """, (project_id,))
            history = [dict(row) for row in cursor.fetchall()]
            return history
    except sqlite3.Error as e:
        logger.error(f"Failed to get history for project {project_id}: {e}")
        return []

def update_task_log(task_id: int, execution_log: str):
    """Updates a task with the execution log and marks it as completed."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tasks SET execution_log = ?, status = 'completed' WHERE id = ?",
                (execution_log, task_id)
            )
            conn.commit()
            logger.info(f"Updated log for task {task_id}.")
    except sqlite3.Error as e:
        logger.error(f"Failed to update log for task {task_id}: {e}")

# --- Main block for testing ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Running database module tests...")
    initialize_database()

    # Test project creation
    print("\n--- Testing Project Creation ---")
    project_id = create_project("Test Project 1")
    if project_id:
        print(f"Project 'Test Project 1' created with ID: {project_id}")
    create_project("Test Project 1") # Test duplicate

    # Test listing projects
    print("\n--- Testing Project Listing ---")
    projects = list_projects()
    print("Available projects:", projects)

    # Test task creation and history
    if projects:
        pid = projects[0]['id']
        print(f"\n--- Testing Task Management for Project ID: {pid} ---")
        task_id = create_task(pid, "Install nginx", "apt-get update\napt-get install nginx -y")
        if task_id:
            print(f"Task created with ID: {task_id}")
            log_data = "[{'command': 'apt-get update', 'returncode': 0, 'stdout': '...', 'stderr': ''}]"
            update_task_log(task_id, log_data)
            print("Task log updated.")

            history = get_project_history(pid)
            print("\nProject history:")
            for item in history:
                print(item)
    print("\nDatabase tests complete.")