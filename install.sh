#!/bin/bash

echo "--- AI Sysadmin Bot Installer ---"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Check for Python 3 and pip
echo "Step 1: Checking for Python 3 and pip..."
if ! command_exists python3; then
    echo "ERROR: Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

if ! command_exists pip3; then
    echo "ERROR: pip3 is not installed. Please install pip3 (e.g., 'sudo apt install python3-pip') and try again."
    exit 1
fi
echo "Python 3 and pip found."

# 2. Create a virtual environment
echo "Step 2: Creating a virtual environment in './venv'..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create a virtual environment."
    exit 1
fi
echo "Virtual environment created."

# 3. Install dependencies
echo "Step 3: Installing dependencies from requirements.txt..."
source venv/bin/activate
pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies."
    deactivate
    exit 1
fi
deactivate
echo "Dependencies installed successfully."

# 4. Create .env file
echo "Step 4: Setting up API keys..."
if [ -f .env ]; then
    echo "An .env file already exists. Skipping creation."
else
    read -p "Please enter your TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN
    read -sp "Please enter your GEMINI_API_KEY: " GEMINI_API_KEY
    echo # for newline after secret input

    echo "Creating .env file..."
    echo "TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}" > .env
    echo "GEMINI_API_KEY=${GEMINI_API_KEY}" >> .env
fi
echo ".env file is configured."

# 5. Make run.sh executable
# We will create run.sh in the next step, but we can make it executable here.
if [ -f run.sh ]; then
    chmod +x run.sh
fi

echo "--- Installation Complete! ---"
echo "To start the bot, you can now use the './run.sh' script."
echo "If you need to change your API keys, you can edit the .env file."