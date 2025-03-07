import streamlit as st
import pandas as pd
import requests
import time
import logging
import openai
from bs4 import BeautifulSoup
import folium
from streamlit_folium import folium_static

# Configure APIs
GOOGLE_MAPS_API_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load surf spots from Excel file
surf_spots_file = "surf_spots.xlsx"  # Ensure this file is available in the deployment
surf_spots_df = pd.read_excel(surf_spots_file)

# Ensure correct columns are used
rename_mapping = {
    "nomSpot": "name",
    "villeSpot": "city",
    "latitude": "latitude",
    "longitude": "longitude",
    "nomSurfForecast": "forecast_name"
}
if "region" in surf_spots_df.columns:
    rename_mapping["region"] = "region"

surf_spots = surf_spots_df.rename(columns=rename_mapping)

# Verify and format Surf-Forecast URLs
def format_forecast_url(name):
    formatted_name = name.replace(" ", "-").capitalize()
    url = f"https://www.surf-forecast.com/breaks/{formatted_name}/forecasts/latest/six_day"
    response = requests.get(url)
    return url if response.status_code == 200 else None

surf_spots["forecast_url"] = surf_spots["forecast_name"].apply(format_forecast_url)

# Function to get travel data from Google Maps API
def get_travel_info(origin, destination_lat, destination_lng):
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin}&destinations={destination_lat},{destination_lng}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url).json()
    try:
        time_text = response["rows"][0]["elements"][0]["duration"]["text"]
        distance_text = response["rows"][0]["elements"][0]["distance"]["text"]
        cost_estimate = 0.15 * float(distance_text.split()[0])  # Approximate cost per km
        return time_text, distance_text, round(cost_estimate, 2)
    except:
        logger.warning(f"Error fetching travel data for {origin} to {destination_lat}, {destination_lng}")
        return "Unknown", "Unknown", "Unknown"

# Function to scrape forecast data (requests only, no Selenium)
def scrape_forecast(url):
    if not url:
        return {"wave_height": "N/A", "wind_speed": "N/A", "tide": "N/A", "swell_period": "N/A"}
    try:
        session = requests.Session()
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = session.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        wave_height = soup.select_one('.forecast-table__wave-height .forecast-table__value')
        wind_speed = soup.select_one('.forecast-table__wind-speed .forecast-table__value')
        tide_info = soup.select_one('.forecast-table__tide .forecast-table__value')
        swell_period = soup.select_one('.forecast-table__wave-period .forecast-table__value')
        return {
            "wave_height": wave_height.text.strip() if wave_height else "N/A",
            "wind_speed": wind_speed.text.strip() if wind_speed else "N/A",
            "tide": tide_info.text.strip() if tide_info else "N/A",
            "swell_period": swell_period.text.strip() if swell_period else "N/A"
        }
    except:
        logger.error(f"Requests-based scraping failed for {url}")
        return {"wave_height": "N/A", "wind_speed": "N/A", "tide": "N/A", "swell_period": "N/A"}

# OpenAI API fallback for missing forecasts
def ai_generate_forecast(location):
    prompt = f"Provide a surf forecast for {location}, including wave height, wind conditions, tide, and swell period. Include best time to surf and ideal wind direction."
    response = openai.Completion.create(
        model="gpt-4",
        prompt=prompt,
        max_tokens=150
    )
    return response["choices"][0]["text"].strip()

# Streamlit UI
st.title("Surf Spot Finder 🌊")
user_location = st.text_input("Enter your starting location (e.g., Paris, France):", "Paris, France")
if "region" in surf_spots.columns:
    region_filter = st.selectbox("Filter by region:", ["All"] + list(surf_spots["region"].unique()))
    filtered_spots = surf_spots if region_filter == "All" else surf_spots[surf_spots["region"] == region_filter]
else:
    filtered_spots = surf_spots

selected_spot = st.selectbox("Choose a surf spot:", filtered_spots["name"])

if st.button("Get Info"):
    spot_data = filtered_spots[filtered_spots["name"] == selected_spot].iloc[0]
    travel_time, travel_distance, travel_cost = get_travel_info(user_location, spot_data["latitude"], spot_data["longitude"])
    forecast = scrape_forecast(spot_data["forecast_url"])
    if forecast["wave_height"] == "N/A":
        forecast_text = ai_generate_forecast(selected_spot)
        st.write(f"AI Forecast: {forecast_text}")
    else:
        rating = "⭐️" * min(int(float(forecast["wave_height"].replace("m", "") or 0)), 5)
        st.write(f"🌊 Wave Height: {forecast['wave_height']} {rating}")
        st.write(f"💨 Wind Speed: {forecast['wind_speed']}")
        st.write(f"🌊 Tide Info: {forecast['tide']}")
        st.write(f"🌊 Swell Period: {forecast['swell_period']}")
        st.write(f"🚗 Travel Time: {travel_time}")
        st.write(f"📏 Distance: {travel_distance}")
        st.write(f"💰 Estimated Cost: {travel_cost}€")
    
    # Display map
    m = folium.Map(location=[spot_data["latitude"], spot_data["longitude"]], zoom_start=6)
    for _, spot in filtered_spots.iterrows():
        folium.Marker(
            [spot["latitude"], spot["longitude"]],
            popup=f"{spot['name']}\nWave Height: {forecast['wave_height']}\nWind Speed: {forecast['wind_speed']}\nTide: {forecast['tide']}\nSwell Period: {forecast['swell_period']}",
        ).add_to(m)
    folium_static(m)
