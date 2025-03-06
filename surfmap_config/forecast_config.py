#!/usr/bin/env python
# coding: utf-8

# # MVP Surfmap
import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import sqlite3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import numpy as np
import time
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_driver():
    """Setup and return a Chrome WebDriver with appropriate options"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        # Execute CDP commands to prevent detection
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        return driver
    except Exception as e:
        logger.error(f"Error setting up Chrome driver: {str(e)}")
        raise

def get_surfSpot_url(nomSurfForecast):
    """
    Donne le contenu web d'une page surf_forecast en utilisant Selenium

    @param nomSurfForecast : nom du spot sur surf_forecast
    """
    urlSurfReport = "https://fr.surf-forecast.com/breaks/" + nomSurfForecast + "/forecasts/latest/six_day"
    driver = None
    
    try:
        logger.info(f"Fetching data for {nomSurfForecast}")
        driver = setup_driver()
        driver.get(urlSurfReport)
        
        # Wait for the page to load completely
        time.sleep(5)  # Give the page time to load
        
        # Wait for the forecast table to load
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CLASS_NAME, "forecast-table__basic"))
            )
        except Exception as e:
            logger.warning(f"Could not find forecast table for {nomSurfForecast}: {str(e)}")
            # Try to get the page source anyway
            contentPage = driver.page_source
            soupContentPage = BeautifulSoup(contentPage, features="html.parser")
            
            # Log the HTML structure for debugging
            logger.debug(f"Page source for {nomSurfForecast}: {soupContentPage.prettify()[:1000]}...")
            return soupContentPage
            
        # Get the page source after JavaScript has rendered
        contentPage = driver.page_source
        soupContentPage = BeautifulSoup(contentPage, features="html.parser")
        return soupContentPage
        
    except Exception as e:
        logger.error(f"Error fetching data for {nomSurfForecast}: {str(e)}")
        return None
    finally:
        if driver:
            driver.quit()

@st.cache_data
def get_dayList_forecast():
    """
    On récupère les jours qui font l'objet de prévision puis on les met en forme
    Le résultat est tel : dayList = ['Vendredi 03', 'Samedi 04', 'Dimanche 05', 'Lundi 06', 'Mardi 07', 'Mercredi 08', 'Jeudi 09', 'Ven 10']

    @param N/A doit être appelée en daily
    """
    soupContentPage = get_surfSpot_url("La-Ciotat")
    if soupContentPage is None:
        return []
        
    try:
        # Try different possible class names for the days row
        resultDays = soupContentPage.find_all("tr", {"class": ["forecast-table__row forecast-table-days", "forecast-table-days"]})
        if not resultDays:
            logger.warning("Could not find forecast days row")
            # Log the HTML structure for debugging
            logger.debug(f"Page structure: {soupContentPage.prettify()[:1000]}...")
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
        logger.error(f"Error getting forecast days: {str(e)}")
        return []

@st.cache_data
def get_infos_surf_report(nomSurfForecast, dayList):
    """
    Récupère et met en forme les forecast pour le spot sélectionné

    @param nomSurfForecast : nom du spot sur surf_forecast
    @dayList : jours sur lesquels chercher le forecast, au format liste
    """
    dict_data_spot = dict()

    try:
        #Import Page Web + jours à travailler
        soupContentPage = get_surfSpot_url(nomSurfForecast)
        if soupContentPage is None:
            logger.warning(f"Could not get data for {nomSurfForecast}")
            return {'No day': 0.0}

        #On récupère le tableau des prévisions
        table = soupContentPage.find_all("tbody", {"class": "forecast-table__basic"})
        if not table:
            logger.warning(f"No forecast table found for {nomSurfForecast}")
            # Log the HTML structure for debugging
            logger.debug(f"Page structure: {soupContentPage.prettify()[:1000]}...")
            return {'No day': 0.0}

        #On récupère ensuite toutes les notations que l'on met en forme
        resultNotations = soupContentPage.find_all("tr", {"class": ["forecast-table__row forecast-table-rating", "forecast-table-rating"]})
        if not resultNotations:
            logger.warning(f"No ratings found for {nomSurfForecast}")
            return {'No day': 0.0}
            
        noteList = []
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
                
                if note is not None:
                    noteList.append(note)
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid rating for {nomSurfForecast}: {str(e)}")
                continue

        if not noteList:
            logger.warning(f"No valid ratings found for {nomSurfForecast}")
            return {'No day': 0.0}

        #On agrège ensuite les résultats sous forme d'un dictionnaire
        index_average = 0
        for day in dayList:
            if index_average + 3 <= len(noteList):
                dict_data_spot[day] = round(np.average(noteList[index_average:index_average+3]), 2)
                index_average += 3
            else:
                dict_data_spot[day] = 0.0

    except Exception as e:
        logger.error(f"Error processing data for {nomSurfForecast}: {str(e)}")
        dict_data_spot['No day'] = 0.0

    return dict_data_spot

@st.cache_data
def load_forecast_data(spot_list, dayList):
    """
    Fait tourner la fonction get_infos_surf_report sur la liste des spots choisis

    @param spot_list : liste des spots à requêter
    @dayList : jours sur lesquels chercher le forecast, au format liste
    """
    #On affiche la barre de chargement
    placeholder_progress_bar = st.empty()
    progress_bar = placeholder_progress_bar.progress(0)
    nb_percent_complete = int(100/len(spot_list))
    iteration = 0

    dict_data_forecast_spot = dict()

    for spot in spot_list:
        try:
            iteration += 1
            logger.info(f"Fetching forecast for {spot}...")
            forecast_spot = get_infos_surf_report(spot, dayList)
            dict_data_forecast_spot[spot] = forecast_spot
            progress_bar.progress(nb_percent_complete*iteration + 1)
            # Add a small delay to avoid being blocked
            time.sleep(3)  # Increased delay to be more conservative
        except Exception as e:
            logger.error(f"Error processing spot {spot}: {str(e)}")
            dict_data_forecast_spot[spot] = {'No day': 0.0}

    placeholder_progress_bar.empty()
    return dict_data_forecast_spot
