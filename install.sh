#!/bin/bash

echo "--- AI Sysadmin Bot Installer ---"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Ensure script is run as root for systemd operations (optional but recommended)
if [ "$EUID" -ne 0 ]; then
    echo "WARNING: Some steps (e.g., systemd service setup) require root privileges."
    echo "You may be prompted for sudo password."
fi

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

# 5. Create run.sh if it doesn't exist
RUN_SCRIPT="./run.sh"
if [ ! -f "$RUN_SCRIPT" ]; then
    echo "Step 5: Creating run.sh..."
    cat > "$RUN_SCRIPT" <<EOF
#!/bin/bash
cd "\$(dirname "\$0")"
source venv/bin/activate
exec python3 bot.py
EOF
    chmod +x "$RUN_SCRIPT"
    echo "run.sh created and made executable."
else
    chmod +x "$RUN_SCRIPT"
    echo "run.sh already exists and is executable."
fi

# 6. Create and enable systemd service (optional, requires sudo)
echo "Step 6: Setting up systemd service..."
SERVICE_NAME="ai-sysadmin-bot.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

# Get absolute path to current directory
INSTALL_DIR="$(pwd)"

cat > "/tmp/$SERVICE_NAME" <<EOF
[Unit]
Description=AI Sysadmin Telegram Bot
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/run.sh
Restart=always
RestartSec=10
EnvironmentFile=$INSTALL_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# Copy to systemd and reload
sudo cp "/tmp/$SERVICE_NAME" "$SERVICE_FILE"
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Systemd service '$SERVICE_NAME' is now active and enabled."
else
    echo "WARNING: Service started but may not be running properly. Check with:"
    echo "  sudo systemctl status $SERVICE_NAME"
fi

echo "--- Installation Complete! ---"
echo "The bot is now running as a systemd service in the background."
echo "To view logs: sudo journalctl -u $SERVICE_NAME -f"
echo "To stop: sudo systemctl stop $SERVICE_NAME"
echo "To disable auto-start: sudo systemctl disable $SERVICE_NAME"
