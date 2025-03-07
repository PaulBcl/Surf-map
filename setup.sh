#!/bin/bash

# Make script exit on first error
set -e

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium
playwright install-deps

# Setup streamlit
echo "Setting up Streamlit..."
mkdir -p ~/.streamlit/

echo "\
[general]\n\
email = \"paul.bacle@gmail.com\"\n\
" > ~/.streamlit/credentials.toml

echo "
[server]\n
headless = true\n
enableCORS=false\n
port = $PORT\n
[theme]\n
primaryColor='#3c5880'\n
backgroundColor='#fafafc'\n
secondaryBackgroundColor='#e6ecf5'\n
textColor='#262730'\n
font='sans serif'\n
" > ~/.streamlit/config.toml
