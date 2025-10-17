import os
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self, api_key):
        """
        Initializes the Gemini client with the provided API key.
        """
        if not api_key:
            raise ValueError("API key for Google Gemini is not provided.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-flash-latest')

    def get_commands(self, task_description: str) -> str:
        """
        Generates a sequence of shell commands based on the task description.
        """
        prompt = f"""
        You are an expert system administrator. Your task is to convert a user's request into a series of executable shell commands for a Linux server.
        The user is running as the root user, so you do not need to use 'sudo'.
        Provide only the shell commands, one per line, without any additional explanations, comments, or formatting like ```bash.

        User request: "{task_description}"

        Commands:
        """

        try:
            logger.info(f"Generating commands for task: '{task_description}'")
            response = self.model.generate_content(prompt)
            commands = response.text.strip()
            logger.info(f"Successfully generated commands.")
            return commands
        except Exception as e:
            logger.error(f"An error occurred while communicating with Gemini API: {e}")
            return ""