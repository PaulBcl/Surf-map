mkdir -p ~/.streamlit/

echo "\
[general]\n\
email = \"paul.bacle@gmail.com\"\n\
" > ~/.streamlit/credentials.toml

echo "[server]
headless = true
port = $PORT
enableCORS = false
[theme]
primaryColor = '#3c5880'
backgroundColor = '#fafafc'
secondaryBackgroundColor = '#e6ecf5'
textColor = '#262730'
font = sans-serif
" > ~/.streamlit/config.toml
