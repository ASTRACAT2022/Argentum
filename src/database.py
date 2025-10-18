import sqlite3
import logging
from typing import List, Dict, Any, Optional
from cryptography.fernet import Fernet
import os

# --- Configuration ---
DB_FILE = "agent_memory.db"
logger = logging.getLogger(__name__)
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if ENCRYPTION_KEY:
    cipher_suite = Fernet(ENCRYPTION_KEY)

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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    programmer_mode INTEGER DEFAULT 0
                )
            """)

            # Add programmer_mode column to projects table if it doesn't exist
            try:
                cursor.execute("ALTER TABLE projects ADD COLUMN programmer_mode INTEGER DEFAULT 0")
                conn.commit()
                logger.info("Column 'programmer_mode' added to 'projects' table.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    pass  # Column already exists
                else:
                    raise

            # Add remote_server_id column to projects table if it doesn't exist
            try:
                cursor.execute("ALTER TABLE projects ADD COLUMN remote_server_id INTEGER")
                conn.commit()
                logger.info("Column 'remote_server_id' added to 'projects' table.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    pass
                else:
                    raise

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

            # SSH Credentials table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ssh_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    host TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    key TEXT NOT NULL
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
            cursor.execute("SELECT id, name, created_at, programmer_mode FROM projects ORDER BY created_at DESC")
            projects = [dict(row) for row in cursor.fetchall()]
            return projects
    except sqlite3.Error as e:
        logger.error(f"Failed to list projects: {e}")
        return []

def set_programmer_mode(project_id: int, enabled: bool):
    """Enables or disables programmer mode for a project."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET programmer_mode = ? WHERE id = ?",
                (1 if enabled else 0, project_id)
            )
            conn.commit()
            logger.info(f"Programmer mode for project {project_id} set to {enabled}.")
    except sqlite3.Error as e:
        logger.error(f"Failed to set programmer mode for project {project_id}: {e}")


def is_programmer_mode_enabled(project_id: int) -> bool:
    """Checks if programmer mode is enabled for a project."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT programmer_mode FROM projects WHERE id = ?", (project_id,))
            result = cursor.fetchone()
            if result:
                return bool(result[0])
            return False
    except sqlite3.Error as e:
        logger.error(f"Failed to check programmer mode for project {project_id}: {e}")
        return False


def set_project_remote_server(project_id: int, credential_id: int):
    """Associates a remote server with a project."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE projects SET remote_server_id = ? WHERE id = ?",
                (credential_id, project_id)
            )
            conn.commit()
            logger.info(f"Project {project_id} associated with remote server {credential_id}.")
    except sqlite3.Error as e:
        logger.error(f"Failed to associate remote server with project {project_id}: {e}")

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

def get_project_id_from_task(task_id: int) -> Optional[int]:
    """Retrieves the project ID for a given task ID."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT project_id FROM tasks WHERE id = ?", (task_id,))
            result = cursor.fetchone()
            if result:
                return result[0]
            return None
    except sqlite3.Error as e:
        logger.error(f"Failed to get project ID for task {task_id}: {e}")
        return None

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

# --- SSH Credential Management ---

def _encrypt(text: str) -> bytes:
    """Encrypts a string."""
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not set.")
    return cipher_suite.encrypt(text.encode())

def _decrypt(encrypted_text: bytes) -> str:
    """Decrypts a string."""
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY not set.")
    return cipher_suite.decrypt(encrypted_text).decode()

def add_ssh_credential(name: str, host: str, port: int, username: str, key: str) -> Optional[int]:
    """Adds new SSH credentials to the database."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            encrypted_key = _encrypt(key)
            cursor.execute(
                "INSERT INTO ssh_credentials (name, host, port, username, key) VALUES (?, ?, ?, ?, ?)",
                (name, host, port, username, encrypted_key)
            )
            conn.commit()
            cred_id = cursor.lastrowid
            logger.info(f"Added SSH credential '{name}' with ID {cred_id}.")
            return cred_id
    except sqlite3.IntegrityError:
        logger.warning(f"SSH credential with name '{name}' already exists.")
        return None
    except Exception as e:
        logger.error(f"Failed to add SSH credential '{name}': {e}")
        return None

def list_ssh_credentials() -> List[Dict[str, Any]]:
    """Lists all SSH credentials."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, host, port, username FROM ssh_credentials ORDER BY name")
            credentials = [dict(row) for row in cursor.fetchall()]
            return credentials
    except sqlite3.Error as e:
        logger.error(f"Failed to list SSH credentials: {e}")
        return []

def get_ssh_credential(credential_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single SSH credential by its ID."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ssh_credentials WHERE id = ?", (credential_id,))
            credential = dict(cursor.fetchone())
            credential['key'] = _decrypt(credential['key'])
            return credential
    except Exception as e:
        logger.error(f"Failed to get SSH credential with ID {credential_id}: {e}")
        return None

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