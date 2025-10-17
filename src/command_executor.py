import subprocess
import logging

logger = logging.getLogger(__name__)

def execute_commands(commands: list[str]) -> list[dict]:
    """
    Executes a list of shell commands and captures their output.

    Args:
        commands: A list of shell commands to execute.

    Returns:
        A list of dictionaries, where each dictionary contains the
        command, its stdout, stderr, and return code.
    """
    results = []
    for command in commands:
        if not command.strip():
            continue

        logger.info(f"Executing command: {command}")
        try:
            # We use shell=True to interpret the command as a full shell command.
            # This is necessary for commands with pipes or other shell features.
            # It's important that we only run commands that have been approved by the user.
            process = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                check=False  # We set check=False to handle non-zero exit codes manually
            )
            result = {
                "command": command,
                "stdout": process.stdout.strip(),
                "stderr": process.stderr.strip(),
                "returncode": process.returncode,
            }
            logger.info(f"Command executed with return code {process.returncode}")
        except Exception as e:
            logger.error(f"Failed to execute command '{command}': {e}")
            result = {
                "command": command,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }
        results.append(result)
    return results

if __name__ == '__main__':
    # Test the executor with some sample commands
    logging.basicConfig(level=logging.INFO)

    # Test 1: A simple successful command
    print("--- Test 1: Successful command ---")
    test_commands_1 = ["echo 'Hello, World!'", "ls -l"]
    outputs_1 = execute_commands(test_commands_1)
    for out in outputs_1:
        print(f"Command: {out['command']}")
        print(f"Return Code: {out['returncode']}")
        print(f"Stdout: {out['stdout']}")
        print(f"Stderr: {out['stderr']}\n")

    # Test 2: A command that produces an error
    print("--- Test 2: Command with an error ---")
    test_commands_2 = ["ls non_existent_directory"]
    outputs_2 = execute_commands(test_commands_2)
    for out in outputs_2:
        print(f"Command: {out['command']}")
        print(f"Return Code: {out['returncode']}")
        print(f"Stdout: {out['stdout']}")
        print(f"Stderr: {out['stderr']}\n")

    # Test 3: A command that might require sudo (will fail without it)
    # This demonstrates how the executor captures permission errors.
    print("--- Test 3: Command requiring privileges ---")
    test_commands_3 = ["apt-get update"] # This will likely fail without sudo
    outputs_3 = execute_commands(test_commands_3)
    for out in outputs_3:
        print(f"Command: {out['command']}")
        print(f"Return Code: {out['returncode']}")
        print(f"Stdout: {out['stdout']}")
        print(f"Stderr: {out['stderr']}\n")