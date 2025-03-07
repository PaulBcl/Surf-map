# Surfmap

A Streamlit application that helps surfers find and plan trips to surf spots, including route information and costs.

We'll get there slowly!

## Features

- Interactive map showing surf spots
- Route planning with Google Maps integration
- Cost calculation including fuel and tolls
- Surf spot information and details

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your Google Maps API key:
   - Get a Google Maps API key from the [Google Cloud Console](https://console.cloud.google.com/)
   - Enable the following APIs:
     - Geocoding API
     - Directions API
   - For local development, create a `.streamlit/secrets.toml` file:
     ```toml
     google_maps_api_key = "your_api_key_here"
     ```

## Running the App

1. Start the Streamlit app:
   ```bash
   streamlit run surf_map.py
   ```

2. Open your browser and navigate to the URL shown in the terminal (typically http://localhost:8501)

## Deployment

The app is configured for deployment on Streamlit Cloud:

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Add your Google Maps API key in the Streamlit Cloud secrets section
5. Deploy!

## Security Notes

- Never commit your `.streamlit/secrets.toml` file to GitHub
- Keep your API keys secure and restrict them to appropriate domains
- The `.gitignore` file is configured to exclude sensitive files

## License

[Your chosen license]
