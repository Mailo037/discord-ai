#!/bin/bash

echo "=========================================="
echo "Checking/Installing dependencies for Linux..."
echo "=========================================="

# Check if python3 is installed
if ! command -v python3 &> /dev/null
then
    echo "[ERROR] python3 could not be found. Please install it."
    exit 1
fi

# Install requirements
python3 -m pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Installation failed. Maybe try: sudo apt install python3-pip"
    exit 1
fi

echo ""
echo "[INFO] Dependencies installed successfully! ✅"
echo "[INFO] Starting the bot..."
echo "=========================================="
echo ""

python3 bot.py
