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
from typing import Optional, Dict, List, Union, Any
from dataclasses import dataclass
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

# Fetch surf forecast data

def get_surfSpot_url(nomSurfForecast: str) -> Optional[str]:
    """Get the surf forecast URL for a given spot."""
    # Format the spot name for the URL (replace spaces with hyphens, lowercase)
    formatted_spot = nomSurfForecast.strip().replace(' ', '-').lower()
    url = f"https://www.surf-forecast.com/breaks/{formatted_spot}/forecasts/latest/six_day"
    
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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
    }
    try:
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data with requests: {str(e)}")
        return None

@dataclass
class ForecastData:
    rating: int
    wave_height: str
    wave_period: str
    wave_energy: str
    wind_speed: str
    timestamp: datetime

def extract_forecast_data(nomSurfForecast: str) -> Dict[str, Union[List[ForecastData], str]]:
    content = get_surfSpot_url(nomSurfForecast)
    if not content:
        return {'error': 'No data fetched'}
    
    soup = BeautifulSoup(content, 'html.parser')
    forecasts: List[ForecastData] = []
    
    try:
        # Get timestamps
        timestamps = soup.select('.forecast-table__header-row time')
        times = [datetime.fromisoformat(t['datetime']) if t.get('datetime') else None for t in timestamps]
        
        # Get all data rows
        rows = soup.select('.forecast-table__basic tr')
        for i in range(len(times)):
            try:
                # Rating (out of 10)
                rating_img = soup.select('.forecast-table-rating img')[i]
                rating = int(rating_img.get('alt', 0))
                
                # Wave height
                wave_height = soup.select('.forecast-table__wave-height .forecast-table__value')[i].text.strip()
                
                # Wave period
                wave_period = soup.select('.forecast-table__wave-period .forecast-table__value')[i].text.strip()
                
                # Wave energy
                wave_energy = soup.select('.forecast-table__wave-energy .forecast-table__value')[i].text.strip()
                
                # Wind speed (km/h)
                wind_speed = soup.select('.forecast-table__wind .forecast-table__value')[i].text.strip()
                
                # Create forecast data point
                forecast = ForecastData(
                    rating=rating,
                    wave_height=wave_height,
                    wave_period=wave_period,
                    wave_energy=wave_energy,
                    wind_speed=wind_speed,
                    timestamp=times[i] if times[i] else datetime.now()
                )
                forecasts.append(forecast)
                
            except (IndexError, ValueError, AttributeError) as e:
                logger.warning(f"Error parsing forecast at index {i}: {str(e)}")
                continue
        
        if not forecasts:
            return {'error': 'No valid forecast data found'}
            
        return {
            'forecasts': forecasts,
            'spot_name': nomSurfForecast,
            'total_forecasts': len(forecasts)
        }
        
    except Exception as e:
        logger.error(f"Error parsing forecast data for {nomSurfForecast}: {str(e)}")
        return {'error': f'Failed to parse forecast data: {str(e)}'}

def validate_forecast_data(data: Dict[str, Any]) -> bool:
    """Validate the structure and content of forecast data."""
    if 'error' in data:
        return False
        
    if not isinstance(data.get('forecasts'), list):
        return False
        
    for forecast in data['forecasts']:
        if not isinstance(forecast, ForecastData):
            return False
        if not all(hasattr(forecast, attr) for attr in ['rating', 'wave_height', 'wave_period', 'wave_energy', 'wind_speed', 'timestamp']):
            return False
            
    return True

def get_dayList_forecast() -> List[str]:
    """Get list of forecast days in the correct format."""
    # List of sample spots to try (these are verified working spots)
    sample_spots = [
        "La-Torche",
        "Biarritz-Grande-Plage",
        "Hossegor-La-Graviere",
        "Lacanau-Ocean"
    ]
    
    for spot in sample_spots:
        try:
            data = extract_forecast_data(spot)
            if not data.get('error'):
                days = []
                for forecast in data['forecasts']:
                    day_str = forecast.timestamp.strftime('%A %d')
                    if day_str not in days:
                        days.append(day_str)
                if days:  # Only return if we got some days
                    logger.info(f"Successfully got forecast days from {spot}")
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
                
            spot_forecasts = {}
            for forecast in data['forecasts']:
                # Format the date to match the day_list format
                day_str = forecast.timestamp.strftime('%A %d')  # e.g. "Monday 15"
                # Find matching day in day_list (handle partial matches)
                matching_day = next((d for d in day_list if day_str in d), None)
                if matching_day:
                    spot_forecasts[matching_day] = float(forecast.rating)
                    
            # Fill in missing days with 0.0
            for day in day_list:
                if day not in spot_forecasts:
                    spot_forecasts[day] = 0.0
                    
            forecasts[spot] = spot_forecasts
            
        except Exception as e:
            logger.error(f"Failed to get forecast for {spot}: {str(e)}")
            forecasts[spot] = {day: 0.0 for day in day_list}  # Use 0.0 as default rating
            continue
            
    return forecasts

# Example usage
if __name__ == "__main__":
    nomSurfForecast = "Penthievre"
    forecast_data = extract_forecast_data(nomSurfForecast)
    if validate_forecast_data(forecast_data):
        print("Valid forecast data retrieved:")
        for forecast in forecast_data['forecasts']:
            print(f"Time: {forecast.timestamp}")
            print(f"Rating: {forecast.rating}/10")
            print(f"Wave Height: {forecast.wave_height}")
            print(f"Wave Period: {forecast.wave_period}")
            print(f"Wave Energy: {forecast.wave_energy}")
            print(f"Wind Speed: {forecast.wind_speed}")
            print("---")
    else:
        print(f"Error: {forecast_data.get('error', 'Unknown error')}")
