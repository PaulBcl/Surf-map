#!/usr/bin/env python
# coding: utf-8

import pandas as pd
import streamlit as st
import numpy as np
import time
import logging
import requests
import asyncio
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import Optional, Dict, List
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import openai
from datetime import datetime, timedelta

# OpenAI API Key (Make sure to store it securely in Streamlit secrets)
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Selenium WebDriver for JavaScript-loaded pages
def init_selenium():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

# Create an HTTP session with retry logic
def create_session():
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Format surf spot name for URL
def format_surf_forecast_url(nomSurfForecast):
    return '-'.join([word.capitalize() for word in nomSurfForecast.split('-')])

# Check if the surf spot URL exists before scraping
def check_url_exists(nomSurfForecast: str) -> bool:
    formatted_name = format_surf_forecast_url(nomSurfForecast)
    url = f"https://www.surf-forecast.com/breaks/{formatted_name}/forecasts/latest/six_day"
    session = create_session()
    response = session.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    return response.status_code != 404

# Fetch surf forecast data with requests or Selenium
def get_surfSpot_url(nomSurfForecast: str) -> Optional[str]:
    formatted_name = format_surf_forecast_url(nomSurfForecast)
    url = f"https://www.surf-forecast.com/breaks/{formatted_name}/forecasts/latest/six_day"

    # Try requests first
    session = create_session()
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException:
        logger.warning(f"Requests failed for {nomSurfForecast}, switching to Selenium")

    # Try Selenium as a fallback for JavaScript-rendered pages
    try:
        driver = init_selenium()
        driver.get(url)
        time.sleep(5)  # Allow time for JavaScript to load
        content = driver.page_source
        driver.quit()
        return content
    except Exception as e:
        logger.error(f"Error with Selenium for {nomSurfForecast}: {str(e)}")
        return None

# AI-powered extraction for missing data
def ai_extract_forecast(content: str) -> Dict:
    prompt = f"Extract surf forecast details (ratings, wave heights, wave periods, wave energy, wind speed) from the following HTML: {content[:1000]}... (truncated)"
    response = openai.Completion.create(
        model="gpt-4",
        prompt=prompt,
        max_tokens=500
    )
    return response["choices"][0]["text"].strip()

# Extract forecast data
def extract_forecast_data(nomSurfForecast: str) -> Dict:
    content = get_surfSpot_url(nomSurfForecast)
    if not content:
        logger.warning(f"No data fetched for {nomSurfForecast}, using AI extraction")
        return ai_extract_forecast("No data available")

    soup = BeautifulSoup(content, 'html.parser')
    data = {}

    try:
        def extract_data(selector):
            elements = soup.select(selector)
            return [el.text.strip() if el else "N/A" for el in elements]

        # Extracting surf forecast data
        data['ratings'] = extract_data('.forecast-table-rating img')
        data['wave_heights'] = extract_data('.forecast-table__wave-height .forecast-table__value')
        data['wave_periods'] = extract_data('.forecast-table__wave-period .forecast-table__value')
        data['wave_energies'] = extract_data('.forecast-table__wave-energy .forecast-table__value')
        data['wind_speeds'] = extract_data('.forecast-table__wind-speed .forecast-table__value')

        for key, value in data.items():
            if all(v == "N/A" for v in value):
                logger.warning(f"Missing {key} for {nomSurfForecast}, using AI")
                data[key] = ai_extract_forecast(content)

    except Exception as e:
        logger.error(f"Error parsing forecast data for {nomSurfForecast}: {str(e)}")
        return {'error': f'Parsing error: {str(e)}'}

    return data

# Example usage
if __name__ == "__main__":
    nomSurfForecast = "penthievre"
    forecast_data = extract_forecast_data(nomSurfForecast)
    print(forecast_data)

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_forecast_data(spot_names: List[str], day_list: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Load forecast data for multiple spots.
    
    Args:
        spot_names: List of spot names to get forecasts for
        day_list: List of days to get forecasts for
        
    Returns:
        Dictionary mapping spot names to their forecast data by day
    """
    if not spot_names or not day_list:
        logger.warning("Empty spot names or day list provided")
        return {}
        
    forecasts = {}
    
    # Process each spot
    for spot in spot_names:
        if not spot:  # Skip empty spot names
            continue
            
        try:
            # Get the forecast data using our new function
            forecast_data = extract_forecast_data(spot)
            
            if 'error' in forecast_data:
                logger.warning(f"Error getting forecast for {spot}: {forecast_data['error']}")
                forecasts[spot] = {day: 0.0 for day in day_list}  # Use 0.0 as default rating
                continue
                
            # Create a mapping of ratings to days
            spot_forecasts = {}
            ratings = forecast_data.get('ratings', [])
            
            # Ensure we have enough ratings for each day
            if len(ratings) >= len(day_list):
                for i, day in enumerate(day_list):
                    try:
                        # Convert rating to float, handling any non-numeric values
                        rating = float(ratings[i]) if ratings[i] != "N/A" else 0.0
                        spot_forecasts[day] = rating
                    except (ValueError, TypeError):
                        spot_forecasts[day] = 0.0
            else:
                logger.warning(f"Insufficient ratings data for {spot}")
                spot_forecasts = {day: 0.0 for day in day_list}
                
            forecasts[spot] = spot_forecasts
            
        except Exception as e:
            logger.error(f"Failed to get forecast for {spot}: {str(e)}")
            forecasts[spot] = {day: 0.0 for day in day_list}  # Use 0.0 as default rating
            continue
            
    return forecasts

def get_dayList_forecast() -> List[str]:
    """
    Get list of forecast days in the correct format.
    Returns a list of the next 7 days in the format 'Day DD' (e.g., 'Monday 15').
    """
    try:
        days = []
        today = datetime.now()
        for i in range(7):
            day = today + timedelta(days=i)
            days.append(day.strftime('%A %d'))
        return days
    except Exception as e:
        logger.error(f"Error generating forecast days: {str(e)}")
        # Return default days if there's an error
        return ['Monday 01', 'Tuesday 02', 'Wednesday 03', 'Thursday 04', 
                'Friday 05', 'Saturday 06', 'Sunday 07']
