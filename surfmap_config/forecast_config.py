#!/usr/bin/env python
# coding: utf-8

# # MVP Surfmap
import pandas as pd
import streamlit as st
import numpy as np
import time
import logging
import asyncio
from typing import Optional, Dict, List
import json
import os
import sys
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flag to control whether to use Playwright or fallback to requests
USE_PLAYWRIGHT = False

# Try to import Playwright - if it fails, we'll use requests instead
try:
    from playwright.sync_api import sync_playwright
    # Check if we can initialize Playwright
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
    
    # Set the flag based on Playwright availability
    USE_PLAYWRIGHT = check_playwright_availability()
except ImportError:
    logger.warning("Playwright not available, using requests-based scraping")
    USE_PLAYWRIGHT = False

def create_session():
    """Create a requests session with retry logic"""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def setup_browser_context(playwright):
    """Setup a browser context with stealth mode"""
    if not USE_PLAYWRIGHT:
        return None, None
        
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
        ]
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    )
    return browser, context

def get_surfSpot_url_with_requests(nomSurfForecast: str) -> Optional[BeautifulSoup]:
    """Get surf spot data using requests and BeautifulSoup"""
    url = f"https://fr.surf-forecast.com/breaks/{nomSurfForecast}/forecasts/latest/six_day"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'fr,fr-FR;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }
    
    try:
        session = create_session()
        response = session.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        # Parse the response content
        soup = BeautifulSoup(response.content, features="html.parser")
        
        # Check if we got a valid page
        if "Access denied" in soup.text or "Please verify you are a human" in soup.text:
            logger.warning(f"Access denied for {nomSurfForecast}")
            return None
            
        return soup
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data for {nomSurfForecast}: {str(e)}")
        return None

def get_surfSpot_url_with_playwright(nomSurfForecast: str) -> Optional[str]:
    """Get surf spot data using Playwright"""
    if not USE_PLAYWRIGHT:
        return None
        
    url = f"https://fr.surf-forecast.com/breaks/{nomSurfForecast}/forecasts/latest/six_day"
    
    with sync_playwright() as playwright:
        try:
            browser, context = setup_browser_context(playwright)
            if not browser or not context:
                return None
                
            page = context.new_page()
            
            # Add error handling for navigation
            response = page.goto(url, wait_until='networkidle', timeout=30000)
            if not response or response.status >= 400:
                logger.error(f"Failed to load page for {nomSurfForecast}: {response.status if response else 'No response'}")
                return None
            
            # Wait for the forecast table to be visible
            page.wait_for_selector('.forecast-table__basic', timeout=10000)
            
            # Get the page content
            content = page.content()
            
            return content
            
        except Exception as e:
            logger.error(f"Error fetching data for {nomSurfForecast} with Playwright: {str(e)}")
            return None
        finally:
            if 'browser' in locals() and browser:
                browser.close()

def get_surfSpot_url(nomSurfForecast: str) -> Optional[str]:
    """
    Donne le contenu web d'une page surf_forecast using either Playwright or requests
    
    @param nomSurfForecast : nom du spot sur surf_forecast
    """
    if USE_PLAYWRIGHT:
        try:
            content = get_surfSpot_url_with_playwright(nomSurfForecast)
            if content:
                return content
            else:
                # If Playwright fails, try requests as fallback
                logger.warning(f"Playwright failed for {nomSurfForecast}, trying requests fallback")
                soup = get_surfSpot_url_with_requests(nomSurfForecast)
                if soup:
                    return str(soup)
                return None
        except Exception as e:
            logger.error(f"Error with Playwright, falling back to requests: {str(e)}")
            soup = get_surfSpot_url_with_requests(nomSurfForecast)
            if soup:
                return str(soup)
            return None
    else:
        # Use requests directly if Playwright is disabled
        soup = get_surfSpot_url_with_requests(nomSurfForecast)
        if soup:
            return str(soup)
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_dayList_forecast() -> List[str]:
    """
    On récupère les jours qui font l'objet de prévision puis on les met en forme
    """
    content = get_surfSpot_url("La-Ciotat")
    if not content:
        return []
        
    if USE_PLAYWRIGHT:
        try:
            with sync_playwright() as playwright:
                browser, context = setup_browser_context(playwright)
                if not browser or not context:
                    # Fall back to BeautifulSoup
                    raise Exception("Playwright browser initialization failed")
                    
                page = context.new_page()
                
                # Set content and wait for it to load
                page.set_content(content)
                
                # Extract days using Playwright's evaluation
                days = page.eval_on_selector_all('.forecast-table-days__content', """
                    (elements) => elements.map(el => {
                        const values = el.querySelectorAll('.forecast-table__value');
                        if (values.length >= 2) {
                            return values[0].textContent.trim() + ' ' + values[1].textContent.trim();
                        }
                        return null;
                    }).filter(day => day !== null)
                """)
                
                browser.close()
                
                if days and len(days) > 0:
                    return days
                # Fall back to BeautifulSoup if no days found
        except Exception as e:
            logger.error(f"Error getting forecast days with Playwright: {str(e)}")
            # Fall back to BeautifulSoup
    
    # Use BeautifulSoup as fallback or primary method if Playwright is disabled
    try:
        soup = BeautifulSoup(content, 'html.parser')
        # Try different possible class names for the days row
        resultDays = soup.find_all("tr", {"class": ["forecast-table__row forecast-table-days", "forecast-table-days"]})
        if not resultDays:
            logger.warning("Could not find forecast days row")
            return []
            
        dayList = []
        for result in resultDays[0].find_all("div", {"class": "forecast-table-days__content"}):
            try:
                day = result.find_all("div", {"class": "forecast-table__value"})
                if len(day) >= 2:
                    dayList.append(day[0].get_text().strip() + " " + day[1].get_text().strip())
            except Exception as e:
                logger.warning(f"Error parsing day: {str(e)}")
                continue
                
        return dayList
    except Exception as e:
        logger.error(f"Error getting forecast days with BeautifulSoup: {str(e)}")
        return []

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_infos_surf_report(nomSurfForecast: str, dayList: List[str]) -> Dict:
    """
    Récupère et met en forme les forecast pour le spot sélectionné
    """
    dict_data_spot = {}
    content = get_surfSpot_url(nomSurfForecast)
    
    if not content:
        return {'No day': 0.0}

    noteList = []
    
    if USE_PLAYWRIGHT:
        try:
            with sync_playwright() as playwright:
                browser, context = setup_browser_context(playwright)
                if not browser or not context:
                    # Fall back to BeautifulSoup
                    raise Exception("Playwright browser initialization failed")
                    
                page = context.new_page()
                
                # Set content and wait for it to load
                page.set_content(content)
                
                # Extract ratings using Playwright's evaluation
                ratings = page.eval_on_selector_all('.forecast-table__row.forecast-table-rating img', """
                    (elements) => elements.map(el => {
                        if (el.alt) return parseInt(el.alt);
                        if (el.title) return parseInt(el.title);
                        if (el.dataset.rating) return parseInt(el.dataset.rating);
                        const src = el.src;
                        if (src && src.includes('rating_')) {
                            const match = src.match(/rating_(\\d+)/);
                            if (match) return parseInt(match[1]);
                        }
                        return null;
                    }).filter(rating => rating !== null)
                """)
                
                browser.close()
                
                if ratings and len(ratings) > 0:
                    noteList = ratings
                else:
                    # Fall back to BeautifulSoup if no ratings found
                    logger.warning(f"No ratings found with Playwright for {nomSurfForecast}, trying BeautifulSoup")
        except Exception as e:
            logger.error(f"Error processing data with Playwright for {nomSurfForecast}: {str(e)}")
            # Fall back to BeautifulSoup
    
    # Use BeautifulSoup as fallback or primary method if Playwright is disabled or failed
    if not noteList:
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Check if we have a valid forecast table
            table = soup.find_all("tbody", {"class": "forecast-table__basic"})
            if not table:
                logger.warning(f"No forecast table found for {nomSurfForecast}")
                return {'No day': 0.0}
    
            # Get all the ratings
            resultNotations = soup.find_all("tr", {"class": ["forecast-table__row forecast-table-rating", "forecast-table-rating"]})
            if not resultNotations:
                logger.warning(f"No ratings found for {nomSurfForecast}")
                return {'No day': 0.0}
                
            # Try different ways to find the rating images
            rating_images = resultNotations[0].find_all("img", {"class": ["rating", "forecast-table__rating"]})
            if not rating_images:
                rating_images = resultNotations[0].find_all("img")
                
            for img in rating_images:
                try:
                    # Try different attributes that might contain the rating
                    note = None
                    if 'alt' in img.attrs:
                        note = int(img['alt'])
                    elif 'title' in img.attrs:
                        note = int(img['title'])
                    elif 'data-rating' in img.attrs:
                        note = int(img['data-rating'])
                    elif 'src' in img.attrs:
                        # Try to extract rating from image URL if it contains it
                        src = img['src']
                        if 'rating_' in src:
                            try:
                                note = int(src.split('rating_')[1].split('.')[0])
                            except (ValueError, IndexError):
                                pass
                    
                    if note is not None:
                        noteList.append(note)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Invalid rating for {nomSurfForecast}: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"Error processing data with BeautifulSoup for {nomSurfForecast}: {str(e)}")
    
    if not noteList:
        logger.warning(f"No valid ratings found for {nomSurfForecast}")
        return {'No day': 0.0}

    # Calculate averages for each day
    index_average = 0
    for day in dayList:
        if index_average + 3 <= len(noteList):
            dict_data_spot[day] = round(np.average(noteList[index_average:index_average+3]), 2)
            index_average += 3
        else:
            dict_data_spot[day] = 0.0

    return dict_data_spot

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_forecast_data(spot_list: List[str], dayList: List[str]) -> Dict:
    """
    Fait tourner la fonction get_infos_surf_report sur la liste des spots choisis
    """
    placeholder_progress_bar = st.empty()
    progress_bar = placeholder_progress_bar.progress(0)
    nb_percent_complete = int(100/len(spot_list))
    iteration = 0

    dict_data_forecast_spot = {}

    for spot in spot_list:
        try:
            iteration += 1
            st.write(f"Fetching forecast for {spot}...")
            forecast_spot = get_infos_surf_report(spot, dayList)
            dict_data_forecast_spot[spot] = forecast_spot
            progress_bar.progress(nb_percent_complete*iteration + 1)
            # Add a small delay to avoid being blocked
            time.sleep(2)
        except Exception as e:
            logger.error(f"Error processing spot {spot}: {str(e)}")
            dict_data_forecast_spot[spot] = {'No day': 0.0}

    placeholder_progress_bar.empty()
    return dict_data_forecast_spot
