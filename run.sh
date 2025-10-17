#!/bin/bash

# This script activates the virtual environment and runs the bot.

# Check if the virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Please run the install.sh script first."
    exit 1
fi

# Activate the virtual environment
source venv/bin/activate

# Run the bot
echo "Starting the AI Sysadmin Bot..."
python3 src/telegram_bot.py

# Deactivate the virtual environment on exit
deactivate
echo "Bot has been stopped."