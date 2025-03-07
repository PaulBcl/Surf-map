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
def format_surf_forecast_url(nomSurfForecast: str) -> str:
    """
    Formats the surf spot name correctly for Surf-Forecast URLs.
    Special cases are handled through a mapping dictionary.
    """
    # Special cases mapping
    special_cases = {
        "plagedu-loch": "Plage-du-Loch",
        "plouharnel-la-guerite-tata-beach": "Plouharnel",
        "pointedu-couregan": "Pointe-du-Couregan",
        "port-bara": "Port-Bara",
        "port-rhu": "Port-Rhu",
        "sainte-barbe": "Sainte-Barbe",
        "thoulars": "Thoulars",
        "penthievre": "Penthievre"
    }
    
    # Convert to lowercase for comparison
    spot_lower = nomSurfForecast.lower()
    
    # Check if it's a special case
    if spot_lower in special_cases:
        return special_cases[spot_lower]
    
    # General case: capitalize each part and join with hyphens
    parts = spot_lower.split('-')
    formatted_parts = []
    for part in parts:
        # Handle multi-word parts (e.g., "la guerite")
        words = part.split()
        formatted_words = [word.capitalize() for word in words]
        formatted_parts.append(' '.join(formatted_words))
    
    return '-'.join(formatted_parts)

# Fetch surf forecast data
def get_surfSpot_url(nomSurfForecast: str) -> Optional[str]:
    """
    Gets the URL for a surf spot, with improved error handling and logging.
    """
    formatted_name = format_surf_forecast_url(nomSurfForecast)
    url = f"https://www.surf-forecast.com/breaks/{formatted_name}/forecasts/latest/six_day"
    logger.info(f"Attempting to fetch data from: {url}")
    
    session = create_session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    
    try:
        response = session.get(url, headers=headers, timeout=20)
        if response.status_code == 404:
            logger.warning(f"URL Not Found (404): {url}")
            return None
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data for {formatted_name}: {str(e)}")
        return None

# Extract forecast data with structured parsing and robust error handling
def extract_forecast_data(nomSurfForecast: str) -> Dict:
    content = get_surfSpot_url(nomSurfForecast)
    if not content:
        logger.warning(f"No data fetched for spot: {nomSurfForecast}")
        return {'error': 'No data fetched'}

    logger.info(f"Successfully fetched content for {nomSurfForecast}")
    soup = BeautifulSoup(content, 'html.parser')
    data = {}

    try:
        # Debug: Check if we're getting blocked or if there's a captcha
        if "captcha" in content.lower() or "blocked" in content.lower():
            logger.error("Possible bot detection/blocking")
            return {'error': 'Access blocked - possible bot detection'}

        # Rating (out of 10)
        ratings = soup.select('.forecast-table-rating img')
        logger.info(f"Found {len(ratings)} rating elements")
        logger.info(f"Rating elements: {[img.get('alt') for img in ratings]}")
        data['ratings'] = [int(img.get('alt', 0)) for img in ratings if img.get('alt', '').isdigit()]
        logger.info(f"Parsed ratings: {data['ratings']}")

        # Wave height
        wave_heights = soup.select('.forecast-table__wave-height .forecast-table__value')
        logger.info(f"Found {len(wave_heights)} wave height elements")
        logger.info(f"Wave height elements: {[wh.text.strip() for wh in wave_heights]}")
        data['wave_heights'] = [wh.text.strip() for wh in wave_heights]

        # Wave period
        wave_periods = soup.select('.forecast-table__wave-period .forecast-table__value')
        logger.info(f"Found {len(wave_periods)} wave period elements")
        logger.info(f"Wave period elements: {[wp.text.strip() for wp in wave_periods]}")
        data['wave_periods'] = [wp.text.strip() for wp in wave_periods]

        # Wave energy
        wave_energies = soup.select('.forecast-table__wave-energy .forecast-table__value')
        logger.info(f"Found {len(wave_energies)} wave energy elements")
        logger.info(f"Wave energy elements: {[we.text.strip() for we in wave_energies]}")
        data['wave_energies'] = [we.text.strip() for we in wave_energies]

        # Wind speed
        wind_speeds = soup.select('.forecast-table__wind-speed .forecast-table__value')
        logger.info(f"Found {len(wind_speeds)} wind speed elements")
        logger.info(f"Wind speed elements: {[ws.text.strip() for ws in wind_speeds]}")
        data['wind_speeds'] = [ws.text.strip() for ws in wind_speeds]

        # Debug: Print the first few lines of HTML if no data found
        if not any([data['ratings'], data['wave_heights'], data['wave_periods'], data['wave_energies'], data['wind_speeds']]):
            logger.error("No data found in any category. First 500 chars of HTML:")
            logger.error(content[:500])
            logger.error("\nCSS classes found in document:")
            logger.error([cls for tag in soup.find_all(class_=True) for cls in tag['class']])
            return {'error': 'No data found in HTML'}

        # Validate data completeness
        if not all([data['ratings'], data['wave_heights'], data['wave_periods'], data['wave_energies'], data['wind_speeds']]):
            logger.warning(f"Incomplete data for spot: {nomSurfForecast}")
            logger.warning("Data lengths: " + 
                         f"ratings={len(data['ratings'])}, " +
                         f"wave_heights={len(data['wave_heights'])}, " +
                         f"wave_periods={len(data['wave_periods'])}, " +
                         f"wave_energies={len(data['wave_energies'])}, " +
                         f"wind_speeds={len(data['wind_speeds'])}")
            return {'error': 'Incomplete data fetched'}

    except Exception as e:
        logger.error(f"Error parsing forecast data for {nomSurfForecast}: {str(e)}")
        logger.error("First 500 chars of HTML:")
        logger.error(content[:500])
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
    # Test with a specific spot
    test_spot = "penthievre"
    logger.info(f"\nTesting detailed scraping for spot: {test_spot}")
    
    # Get the URL
    formatted_name = format_surf_forecast_url(test_spot)
    url = f"https://www.surf-forecast.com/breaks/{formatted_name}/forecasts/latest/six_day"
    logger.info(f"Using URL: {url}")
    
    # Get the forecast data with detailed logging
    forecast_data = extract_forecast_data(test_spot)
    
    if 'error' not in forecast_data:
        logger.info("\nSuccessfully retrieved forecast data:")
        for key, value in forecast_data.items():
            logger.info(f"{key}: {value}")
    else:
        logger.error(f"\nError: {forecast_data['error']}")
