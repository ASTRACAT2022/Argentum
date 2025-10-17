import os
import google.generativeai as genai
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("API key for Google Gemini is not provided.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-flash-latest')

    def get_commands(
        self,
        task_description: str,
        history: List[Dict[str, Any]],
        is_programmer_mode: bool,
        last_command_output: Optional[str] = None
    ) -> str:
        """
        Generates a sequence of commands based on the task, history, and mode.
        """
        history_context = ""
        if history:
            history_context += "Here is the history of previous tasks for this project:\n"
            for task in history:
                history_context += f"- Task: {task['description']}\n"
                history_context += f"  - Plan: {task['plan']}\n"
                history_context += f"  - Outcome: {task['status']} (Log: {task['execution_log']})\n"
            history_context += "\n"

        if is_programmer_mode:
            prompt = self._get_programmer_mode_prompt(task_description, history_context, last_command_output)
        else:
            prompt = self._get_standard_mode_prompt(task_description, history_context)

        try:
            logger.info(f"Generating commands for task: '{task_description}'")
            response = self.model.generate_content(prompt)
            commands = response.text.strip()
            logger.info(f"Successfully generated commands:\n{commands}")
            return commands
        except Exception as e:
            logger.error(f"An error occurred while communicating with Gemini API: {e}")
            return ""

    def _get_standard_mode_prompt(self, task_description: str, history_context: str) -> str:
        return f"""
        You are an expert system administrator. Your task is to convert a user's request into a series of executable shell commands for a Linux server.
        The user is running as the root user, so you do not need to use 'sudo'.
        Provide only the shell commands, one per line, without any additional explanations, comments, or formatting like ```bash.

        {history_context}
        Current user request: "{task_description}"

        Commands:
        """

    def _get_programmer_mode_prompt(self, task_description: str, history_context: str, last_command_output: Optional[str]) -> str:
        output_context = ""
        if last_command_output is not None:
            output_context = f"""
            The last command produced the following output. Use this to decide the next step.
            <last_command_output>
            {last_command_output}
            </last_command_output>
            """

        return f"""
        You are an autonomous AI programmer and system administrator. Your goal is to complete the user's task by executing a sequence of commands.
        You operate in a loop: you issue a command, observe the output, and then decide on the next command.

        **Available Commands:**
        1. `SHELL <command>`: Executes a shell command on the Linux server (as root).
        2. `READ_FILE <path>`: Reads the content of a file at the given path.
        3. `WRITE_FILE <path>`: Writes content to a file. The content must be enclosed in a '<<CONTENT' and 'CONTENT' block on new lines.
           Example:
           WRITE_FILE /etc/nginx/nginx.conf
           <<CONTENT
           user www-data;
           worker_processes auto;
           CONTENT
        4. `LIST_FILES <path>`: Lists the files in a directory.
        5. `TASK_COMPLETE`: Issue this command when you are certain the task is fully completed.

        **Your Process:**
        1. **Analyze the Goal:** Understand the user's request: "{task_description}".
        2. **Consult History:** Review the project history: {history_context}
        3. **Observe Output:** Use the output from the previous command to guide your next action: {output_context}
        4. **Formulate Next Command:** Decide on the single best command to execute next to get closer to the goal.
        5. **Repeat:** Continue this loop until the task is complete.

        **Instructions:**
        - Think step-by-step.
        - Only output the *next single command* to be executed. Do not provide explanations or comments.
        - If you need to write a file, make sure the content is correct and complete.

        Based on the current state, what is the next command you will issue?

        Command:
        """