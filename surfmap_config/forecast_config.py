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
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from contextlib import contextmanager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@contextmanager
def get_selenium_driver():
    """
    Context manager for Selenium WebDriver to ensure proper cleanup.
    """
    driver = None
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-features=NetworkService')
        chrome_options.add_argument('--window-size=1920x1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        yield driver
    except Exception as e:
        logger.error(f"Failed to initialize Selenium driver: {str(e)}")
        yield None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.error(f"Error closing Selenium driver: {str(e)}")

# Requests session with retry logic
def create_session():
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

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

def handle_popups(driver):
    """
    Handle various types of popups that might appear on the page.
    """
    try:
        # Common cookie consent and popup button selectors
        popup_selectors = [
            "#onetrust-accept-btn-handler",  # Common cookie accept button
            ".accept-cookies",
            "#accept-cookies",
            ".cookie-notice button",
            ".qc-cmp2-summary-buttons button",  # Quantcast consent button
            ".modal-close",
            ".popup-close",
            ".dialog-close",
            ".overlay-close"
        ]
        
        for selector in popup_selectors:
            try:
                wait = WebDriverWait(driver, 3)  # Short timeout for popup check
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        element.click()
                        logger.info(f"Clicked popup element with selector: {selector}")
                        time.sleep(1)  # Short wait after clicking
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Error handling popups (non-critical): {str(e)}")

def get_surfSpot_url(nomSurfForecast: str) -> Optional[str]:
    """
    Gets the URL for a surf spot using Selenium for JavaScript rendering.
    """
    formatted_name = format_surf_forecast_url(nomSurfForecast)
    url = f"https://www.surf-forecast.com/breaks/{formatted_name}/forecasts/latest/six_day"
    logger.info(f"Attempting to fetch data from: {url}")
    
    with get_selenium_driver() as driver:
        if not driver:
            logger.error("Failed to initialize Selenium driver")
            return None
            
        try:
            # Load the page
            driver.get(url)
            
            # Handle any popups that might block content
            handle_popups(driver)
            
            # Wait for the forecast table to load
            logger.info("Waiting for forecast table to load...")
            wait = WebDriverWait(driver, 20)
            
            # First check if table exists
            table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'forecast-table__basic')))
            
            # Then check if it's visible
            if not table.is_displayed():
                logger.error("Forecast table found but not visible - possible overlay issue")
                # Try handling popups again
                handle_popups(driver)
                if not table.is_displayed():
                    return None
            
            # Get the page source after JavaScript execution
            content = driver.page_source
            
            if "404 Not Found" in content:
                logger.warning(f"URL Not Found (404): {url}")
                return None
            
            # Verify we have the content we need
            if 'forecast-table__basic' not in content:
                logger.error("Forecast table not found in page source")
                return None
                
            return content
            
        except TimeoutException:
            logger.error(f"Timeout waiting for forecast table to load: {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching data with Selenium for {formatted_name}: {str(e)}")
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
        ratings = soup.select('.forecast-table__rating img')  # Updated selector
        logger.info(f"Found {len(ratings)} rating elements")
        logger.info(f"Rating elements: {[img.get('alt') for img in ratings]}")
        data['ratings'] = [int(img.get('alt', 0)) for img in ratings if img.get('alt', '').isdigit()]
        logger.info(f"Parsed ratings: {data['ratings']}")

        # Wave height
        wave_heights = soup.select('.forecast-table__cell--wave-height .forecast-table__value')  # Updated selector
        logger.info(f"Found {len(wave_heights)} wave height elements")
        logger.info(f"Wave height elements: {[wh.text.strip() for wh in wave_heights]}")
        data['wave_heights'] = [wh.text.strip() for wh in wave_heights]

        # Wave period
        wave_periods = soup.select('.forecast-table__cell--wave-period .forecast-table__value')  # Updated selector
        logger.info(f"Found {len(wave_periods)} wave period elements")
        logger.info(f"Wave period elements: {[wp.text.strip() for wp in wave_periods]}")
        data['wave_periods'] = [wp.text.strip() for wp in wave_periods]

        # Wave energy
        wave_energies = soup.select('.forecast-table__cell--wave-energy .forecast-table__value')  # Updated selector
        logger.info(f"Found {len(wave_energies)} wave energy elements")
        logger.info(f"Wave energy elements: {[we.text.strip() for we in wave_energies]}")
        data['wave_energies'] = [we.text.strip() for we in wave_energies]

        # Wind speed
        wind_speeds = soup.select('.forecast-table__cell--wind-speed .forecast-table__value')  # Updated selector
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
