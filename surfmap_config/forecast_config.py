#!/usr/bin/env python
# coding: utf-8

import pandas as pd
import streamlit as st
import numpy as np
import time
import logging
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import Optional, Dict, List
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flag to control whether to use Playwright
USE_PLAYWRIGHT = False

try:
    from playwright.sync_api import sync_playwright
    @st.cache_resource
    def check_playwright_availability():
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                browser.close()
                return True
        except Exception as e:
            logger.warning(f"Playwright initialization failed: {str(e)}")
            return False
    USE_PLAYWRIGHT = check_playwright_availability()
except ImportError:
    logger.warning("Playwright not available, using requests-based scraping")
    USE_PLAYWRIGHT = False

# Requests session with retry logic
def create_session():
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Playwright browser setup
def setup_browser_context(playwright):
    if not USE_PLAYWRIGHT:
        return None, None
    browser = playwright.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
    context = browser.new_context(user_agent='Mozilla/5.0')
    return browser, context

# Format surf forecast name for URL
def format_surf_forecast_url(nomSurfForecast):
    """
    Formats the surf spot name correctly for Surf-Forecast URLs.
    """
    return '-'.join([word.capitalize() for word in nomSurfForecast.split('-')])

# Fetch surf forecast data
def get_surfSpot_url(nomSurfForecast: str) -> Optional[str]:
    formatted_name = format_surf_forecast_url(nomSurfForecast)
    url = f"https://www.surf-forecast.com/breaks/{formatted_name}/forecasts/latest/six_day"
    
    if USE_PLAYWRIGHT:
        try:
            with sync_playwright() as playwright:
                browser, context = setup_browser_context(playwright)
                if not browser or not context:
                    raise Exception("Playwright initialization failed")
                page = context.new_page()
                page.goto(url, wait_until='networkidle', timeout=30000)
                page.wait_for_selector('.forecast-table__basic', timeout=10000)
                content = page.content()
                browser.close()
                return content
        except Exception as e:
            logger.error(f"Error fetching data with Playwright: {str(e)}")
    
    session = create_session()
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = session.get(url, headers=headers, timeout=20)
        if response.status_code == 404:
            logger.warning(f"URL Not Found (404): {url}")
            return None
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data with requests: {str(e)}")
        return None

# Extract forecast data with structured parsing and robust error handling
def extract_forecast_data(nomSurfForecast: str) -> Dict:
    content = get_surfSpot_url(nomSurfForecast)
    if not content:
        logger.warning(f"No data fetched for spot: {nomSurfForecast}")
        return {'error': 'No data fetched'}

    soup = BeautifulSoup(content, 'html.parser')
    data = {}

    try:
        # Rating (out of 10)
        ratings = soup.select('.forecast-table-rating img')
        data['ratings'] = [int(img.get('alt', 0)) for img in ratings if img.get('alt', '').isdigit()]

        # Wave height
        wave_heights = soup.select('.forecast-table__wave-height .forecast-table__value')
        data['wave_heights'] = [wh.text.strip() for wh in wave_heights]

        # Wave period
        wave_periods = soup.select('.forecast-table__wave-period .forecast-table__value')
        data['wave_periods'] = [wp.text.strip() for wp in wave_periods]

        # Wave energy
        wave_energies = soup.select('.forecast-table__wave-energy .forecast-table__value')
        data['wave_energies'] = [we.text.strip() for we in wave_energies]

        # Wind speed (km/h)
        wind_speeds = soup.select('.forecast-table__wind-speed .forecast-table__value')
        data['wind_speeds'] = [ws.text.strip() for ws in wind_speeds]

        # Validate data completeness
        if not all([data['ratings'], data['wave_heights'], data['wave_periods'], data['wave_energies'], data['wind_speeds']]):
            logger.warning(f"Incomplete data for spot: {nomSurfForecast}")
            return {'error': 'Incomplete data fetched'}

    except Exception as e:
        logger.error(f"Error parsing forecast data for {nomSurfForecast}: {str(e)}")
        return {'error': f'Parsing error: {str(e)}'}

    return data

def get_dayList_forecast() -> List[str]:
    """Get list of forecast days in the correct format."""
    # List of sample spots to try (these are verified working spots)
    sample_spots = [
        "penthievre",  # Using lowercase as per new format
        "la-torche",
        "hossegor"
    ]
    
    for spot in sample_spots:
        try:
            data = extract_forecast_data(spot)
            if 'error' not in data and data.get('ratings'):
                # Get the next 7 days
                days = []
                today = datetime.now()
                for i in range(7):
                    day = today + timedelta(days=i)
                    days.append(day.strftime('%A %d'))
                logger.info(f"Successfully generated forecast days")
                return days
            logger.warning(f"Could not get forecast data for {spot}")
        except Exception as e:
            logger.warning(f"Error getting forecast for {spot}: {str(e)}")
            continue
    
    # Fallback: return next 7 days
    logger.warning("Using fallback day list")
    days = []
    today = datetime.now()
    for i in range(7):
        day = today + timedelta(days=i)
        days.append(day.strftime('%A %d'))
    return days

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
    forecasts = {}
    for spot in spot_names:
        if not spot:  # Skip empty spot names
            continue
            
        try:
            data = extract_forecast_data(spot)
            if 'error' in data:
                logger.warning(f"Error getting forecast for {spot}: {data['error']}")
                forecasts[spot] = {day: 0.0 for day in day_list}  # Use 0.0 as default rating
                continue
                
            # Create a mapping of ratings to days
            spot_forecasts = {}
            ratings = data.get('ratings', [])
            
            # Ensure we have enough ratings for each day
            if len(ratings) >= len(day_list):
                for i, day in enumerate(day_list):
                    spot_forecasts[day] = float(ratings[i])
            else:
                logger.warning(f"Insufficient ratings data for {spot}")
                spot_forecasts = {day: 0.0 for day in day_list}
                
            forecasts[spot] = spot_forecasts
            
        except Exception as e:
            logger.error(f"Failed to get forecast for {spot}: {str(e)}")
            forecasts[spot] = {day: 0.0 for day in day_list}  # Use 0.0 as default rating
            continue
            
    return forecasts

# Example usage
if __name__ == "__main__":
    # Test the full pipeline
    nomSurfForecast = "penthievre"  # Using lowercase as per new format
    
    # Test day list generation
    print("Getting forecast days...")
    days = get_dayList_forecast()
    print(f"Forecast days: {days}")
    
    # Test forecast data extraction
    print("\nGetting forecast data...")
    forecast_data = extract_forecast_data(nomSurfForecast)
    
    if 'error' not in forecast_data:
        print("\nRaw forecast data:")
        for key, value in forecast_data.items():
            print(f"{key}: {value}")
            
        # Test forecast loading
        print("\nLoading formatted forecast data...")
        formatted_data = load_forecast_data([nomSurfForecast], days)
        print("\nFormatted forecast data:")
        for spot, forecasts in formatted_data.items():
            print(f"\nSpot: {spot}")
            for day, rating in forecasts.items():
                print(f"{day}: {rating}/10")
    else:
        print(f"\nError: {forecast_data['error']}")
