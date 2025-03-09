# Surfmap

A Streamlit application that helps surfers find and plan trips to surf spots, including route information and costs.

## Features

- Interactive map showing surf spots
- Route planning with Google Maps integration
- Cost calculation including fuel and tolls
- AI-powered surf spot recommendations and ratings
- Real-time surf forecasts using OpenAI's API

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your API keys:
   - Get a Google Maps API key from the [Google Cloud Console](https://console.cloud.google.com/)
     - Enable the following APIs:
       - Geocoding API
       - Directions API
   - Get an OpenAI API key from [OpenAI](https://platform.openai.com/api-keys)
   - For local development, create a `.streamlit/secrets.toml` file:
     ```toml
     google_maps_api_key = "your_google_maps_api_key_here"
     OPENAI_API_KEY = "your_openai_api_key_here"
     ```

## Running the App

1. Start the Streamlit app:
   ```bash
   streamlit run surf_map.py
   ```

2. Open your browser and navigate to the URL shown in the terminal (typically http://localhost:8501)

## How It Works

The application uses several key technologies:

1. **OpenAI API**: 
   - Finds and rates nearby surf spots based on current conditions
   - Provides detailed surf forecasts for each location
   - Analyzes spot characteristics for optimal surfing conditions

2. **Google Maps APIs**:
   - Converts addresses to coordinates
   - Calculates travel times and distances
   - Provides route information and cost estimates

3. **Streamlit**:
   - Creates an interactive web interface
   - Handles user input and filtering
   - Displays the map and surf spot information

## Deployment

The app is configured for deployment on Streamlit Cloud:

1. Push your code to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Add your API keys in the Streamlit Cloud secrets section:
   - Add both `google_maps_api_key` and `OPENAI_API_KEY`
5. Deploy!

## Security Notes

- Never commit your `.streamlit/secrets.toml` file to GitHub
- Keep your API keys secure and restrict them to appropriate domains
- The `.gitignore` file is configured to exclude sensitive files
- Monitor your API usage to control costs

## License

[Your chosen license]
