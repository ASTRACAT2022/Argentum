import subprocess
import logging
import os
from typing import Dict, Any, List
import paramiko

logger = logging.getLogger(__name__)

def _execute_shell(command: str) -> Dict[str, Any]:
    """Executes a single shell command."""
    logger.info(f"Executing shell command: {command}")
    try:
        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
            timeout=180  # 3-minute timeout
        )
        return {
            "command": command,
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
            "returncode": process.returncode,
        }
    except subprocess.TimeoutExpired:
        logger.warning(f"Command '{command}' timed out.")
        return {"command": command, "stdout": "", "stderr": "Command timed out after 3 minutes.", "returncode": -1}
    except Exception as e:
        logger.error(f"Failed to execute command '{command}': {e}")
        return {"command": command, "stdout": "", "stderr": str(e), "returncode": -1}

def _read_file(path: str) -> Dict[str, Any]:
    """Reads the content of a file."""
    logger.info(f"Reading file: {path}")
    try:
        with open(path, 'r') as f:
            content = f.read()
        return {"command": f"READ_FILE {path}", "stdout": content, "stderr": "", "returncode": 0}
    except Exception as e:
        logger.error(f"Failed to read file '{path}': {e}")
        return {"command": f"READ_FILE {path}", "stdout": "", "stderr": str(e), "returncode": 1}

def _write_file(path: str, content: str) -> Dict[str, Any]:
    """Writes content to a file."""
    logger.info(f"Writing to file: {path}")
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return {"command": f"WRITE_FILE {path}", "stdout": f"File '{path}' written successfully.", "stderr": "", "returncode": 0}
    except Exception as e:
        logger.error(f"Failed to write to file '{path}': {e}")
        return {"command": f"WRITE_FILE {path}", "stdout": "", "stderr": str(e), "returncode": 1}

def _list_files(path: str) -> Dict[str, Any]:
    """Lists files in a directory."""
    logger.info(f"Listing files in: {path}")
    try:
        files = os.listdir(path)
        return {"command": f"LIST_FILES {path}", "stdout": "\n".join(files), "stderr": "", "returncode": 0}
    except Exception as e:
        logger.error(f"Failed to list files in '{path}': {e}")
        return {"command": f"LIST_FILES {path}", "stdout": "", "stderr": str(e), "returncode": 1}


def _execute_ssh(command: str, creds: Dict[str, Any]) -> Dict[str, Any]:
    """Executes a single shell command on a remote server."""
    logger.info(f"Executing SSH command: {command} on {creds['host']}")
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        from io import StringIO
        key_file = StringIO(creds['key'])
        pkey = paramiko.RSAKey.from_private_key(key_file)

        client.connect(
            hostname=creds['host'],
            port=creds['port'],
            username=creds['username'],
            pkey=pkey,
            timeout=180
        )

        stdin, stdout, stderr = client.exec_command(command, timeout=180)

        stdout_str = stdout.read().decode('utf-8').strip()
        stderr_str = stderr.read().decode('utf-8').strip()
        returncode = stdout.channel.recv_exit_status()

        client.close()

        return {
            "command": command,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "returncode": returncode,
        }
    except Exception as e:
        logger.error(f"Failed to execute SSH command '{command}': {e}")
        return {"command": command, "stdout": "", "stderr": str(e), "returncode": -1}


def execute_command(full_command: str, ssh_creds: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Parses and executes a command, which can be a shell command or a special command.
    If ssh_creds are provided, it will execute the command on the remote server.
    """
    if not full_command.strip():
        return {"stdout": "", "stderr": "Empty command.", "returncode": 1}

    parts = full_command.split(maxsplit=1)
    command_type = parts[0].upper()
    args = parts[1] if len(parts) > 1 else ""

    if command_type == "SHELL":
        if ssh_creds:
            return _execute_ssh(args, ssh_creds)
        return _execute_shell(args)
    elif command_type == "READ_FILE":
        if ssh_creds:
            return _execute_ssh(f"cat {args}", ssh_creds)
        return _read_file(args)
    elif command_type == "WRITE_FILE":
        if ssh_creds:
            path, content = args.split('\n', 1)
            path = path.strip()
            # Strip the <<CONTENT and CONTENT markers
            if content.startswith("<<CONTENT\n"):
                content = content[len("<<CONTENT\n"):]
            if content.endswith("\nCONTENT"):
                content = content[:-len("\nCONTENT")]
            # Use SFTP to write the file over SSH
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                from io import StringIO
                key_file = StringIO(ssh_creds['key'])
                pkey = paramiko.RSAKey.from_private_key(key_file)

                client.connect(
                    hostname=ssh_creds['host'],
                    port=ssh_creds['port'],
                    username=ssh_creds['username'],
                    pkey=pkey,
                    timeout=180
                )
                sftp = client.open_sftp()
                with sftp.open(path, 'w') as f:
                    f.write(content)
                sftp.close()
                client.close()
                return {"command": f"WRITE_FILE {path}", "stdout": f"File '{path}' written successfully.", "stderr": "", "returncode": 0}
            except Exception as e:
                logger.error(f"Failed to write file over SSH '{path}': {e}")
                return {"command": f"WRITE_FILE {path}", "stdout": "", "stderr": str(e), "returncode": 1}
        try:
            path, content = args.split('\n', 1)
            path = path.strip()
            # Strip the <<CONTENT and CONTENT markers
            if content.startswith("<<CONTENT\n"):
                content = content[len("<<CONTENT\n"):]
            if content.endswith("\nCONTENT"):
                content = content[:-len("\nCONTENT")]
            return _write_file(path, content)
        except ValueError:
            return {"command": f"WRITE_FILE {args}", "stdout": "", "stderr": "Invalid WRITE_FILE format. Missing path or content.", "returncode": 1}
    elif command_type == "LIST_FILES":
        if ssh_creds:
            return _execute_ssh(f"ls -F {args if args else '.'}", ssh_creds)
        return _list_files(args if args else ".")
    else:
        # Default to executing as a shell command for backward compatibility
        return _execute_shell(full_command)

def execute_commands(commands: List[str], ssh_creds: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    Executes a list of commands. This is kept for the standard (non-programmer) mode.
    """
    results = []
    for command in commands:
        results.append(execute_command(command, ssh_creds))
    return results

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("--- Testing Command Executor ---")

    # Test 1: SHELL command
    print("\n--- Test 1: SHELL command ---")
    res1 = execute_command("SHELL echo 'Hello from shell'")
    print(res1)

    # Test 2: READ_FILE command (create a file first)
    print("\n--- Test 2: READ_FILE command ---")
    with open("test_read.txt", "w") as f:
        f.write("Hello from test file")
    res2 = execute_command("READ_FILE test_read.txt")
    print(res2)
    os.remove("test_read.txt")

    # Test 3: WRITE_FILE command
    print("\n--- Test 3: WRITE_FILE command ---")
    write_cmd = """WRITE_FILE test_write.txt
<<CONTENT
This is a test write.
CONTENT"""
    res3 = execute_command(write_cmd)
    print(res3)
    if res3["returncode"] == 0:
        with open("test_write.txt", "r") as f:
            print(f"Content of test_write.txt: {f.read()}")
        os.remove("test_write.txt")

    # Test 4: LIST_FILES command
    print("\n--- Test 4: LIST_FILES command ---")
    res4 = execute_command("LIST_FILES .")
    print(res4)

    # Test 5: Legacy command (no type specified)
    print("\n--- Test 5: Legacy command ---")
    res5 = execute_command("echo 'Legacy hello'")
    print(res5)

    print("\n--- Command Executor Tests Complete ---")