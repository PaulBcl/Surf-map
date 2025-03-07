#!/bin/bash

# Exit on error
set -e

echo "Starting setup..."

# Install system dependencies
echo "Installing system dependencies..."
apt-get update
apt-get install -y wget gnupg2 apt-transport-https ca-certificates

# Install Chrome
echo "Installing Google Chrome..."
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
apt-get update
apt-get install -y google-chrome-stable

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install ChromeDriver using webdriver-manager
echo "Installing ChromeDriver..."
python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"

# Setup streamlit
echo "Setting up Streamlit..."
mkdir -p ~/.streamlit/

echo "\
[general]\n\
email = \"paul.bacle@gmail.com\"\n\
" > ~/.streamlit/credentials.toml

echo "\
[server]\n\
headless = true\n\
enableCORS=false\n\
port = \$PORT\n\
[theme]\n\
primaryColor='#F63366'\n\
backgroundColor='#FFFFFF'\n\
secondaryBackgroundColor='#F0F2F6'\n\
textColor='#262730'\n\
font='sans serif'\n\
" > ~/.streamlit/config.toml

echo "Setup completed successfully!"
