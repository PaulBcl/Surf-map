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
