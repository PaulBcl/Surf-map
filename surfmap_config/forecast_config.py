#!/usr/bin/env python
# coding: utf-8

# # MVP Surfmap
import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import sqlite3
import numpy as np
import time
import logging
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def get_surfSpot_url(nomSurfForecast):
    """
    Donne le contenu web d'une page surf_forecast

    @param nomSurfForecast : nom du spot sur surf_forecast
    """
    urlSurfReport = "https://fr.surf-forecast.com/breaks/" + nomSurfForecast + "/forecasts/latest/six_day"
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
        response = session.get(urlSurfReport, headers=headers, timeout=20)
        response.raise_for_status()
        
        # Parse the response content
        soupContentPage = BeautifulSoup(response.content, features="html.parser")
        
        # Check if we got a valid page
        if "Access denied" in soupContentPage.text or "Please verify you are a human" in soupContentPage.text:
            logger.warning(f"Access denied for {nomSurfForecast}")
            return None
            
        return soupContentPage
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data for {nomSurfForecast}: {str(e)}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
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

@st.cache_data(ttl=3600)  # Cache for 1 hour
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

@st.cache_data(ttl=3600)  # Cache for 1 hour
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
