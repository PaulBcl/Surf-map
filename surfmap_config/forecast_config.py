#!/usr/bin/env python
# coding: utf-8

# # MVP Surfmap
import pandas as pd
import streamlit as st
import requests
from bs4 import BeautifulSoup
import sqlite3
from selenium import webdriver
import numpy as np


def get_surfSpot_url(nomSurfForecast):
    """
    Donne le contenu web d'une page surf_forecast

    @param nomSurfForecast : nom du spot sur surf_forecast
    """
    urlSurfReport = "https://fr.surf-forecast.com/breaks/" + nomSurfForecast + "/forecasts/latest/six_day"
    try:
        pageSurfReport = requests.get(urlSurfReport)
        if pageSurfReport.status_code != 200:
            st.error(f"Failed to fetch data for {nomSurfForecast}. Status code: {pageSurfReport.status_code}")
            return None
        contentPage = pageSurfReport.content
        soupContentPage = BeautifulSoup(contentPage, features = "html.parser")
        return soupContentPage
    except Exception as e:
        st.error(f"Error fetching data for {nomSurfForecast}: {str(e)}")
        return None

@st.cache_data
def get_dayList_forecast():
    """
    On récupère les jours qui font l'objet de prévision puis on les met en forme
    Le résultat est tel : dayList = ['Vendredi 03', 'Samedi 04', 'Dimanche 05', 'Lundi 06', 'Mardi 07', 'Mercredi 08', 'Jeudi 09', 'Ven 10']

    @param N/A doit être appelée en daily
    """
    soupContentPage = get_surfSpot_url("La-Ciotat")
    #print(soupContentPage)
    resultDays = soupContentPage.find_all("tr", {"class": "forecast-table__row forecast-table-days"})[0].find_all("div", {"class": "forecast-table-days__content"})
    table = soupContentPage.find_all("tbody", {"class": "forecast-table__basic"})
    dayList = []
    for result in resultDays:
        try:
            day = result.find_all("div", {"class": "forecast-table__value"})
            dayList.append(day[0].get_text() + " " + day[1].get_text())
        except:
            pass
    return dayList

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
            st.warning(f"Could not get data for {nomSurfForecast}")
            return {'No day': 0.0}

        #On récupère le tableau des prévisions
        table = soupContentPage.find_all("tbody", {"class": "forecast-table__basic"})
        if not table:
            st.warning(f"No forecast table found for {nomSurfForecast}")
            return {'No day': 0.0}

        #On récupère ensuite toutes les notations que l'on met en forme
        resultNotations = soupContentPage.find_all("tr", {"class": "forecast-table__row forecast-table-rating"})
        if not resultNotations:
            st.warning(f"No ratings found for {nomSurfForecast}")
            return {'No day': 0.0}
            
        noteList = []
        for img in resultNotations[0].find_all("img"):
            try:
                note = int(img['alt'])
                noteList.append(note)
            except (ValueError, KeyError) as e:
                st.warning(f"Invalid rating for {nomSurfForecast}: {str(e)}")
                continue

        if not noteList:
            st.warning(f"No valid ratings found for {nomSurfForecast}")
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
        st.error(f"Error processing data for {nomSurfForecast}: {str(e)}")
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
            st.write(f"Fetching forecast for {spot}...")
            forecast_spot = get_infos_surf_report(spot, dayList)
            dict_data_forecast_spot[spot] = forecast_spot
            progress_bar.progress(nb_percent_complete*iteration + 1)
        except Exception as e:
            st.error(f"Error processing spot {spot}: {str(e)}")
            dict_data_forecast_spot[spot] = {'No day': 0.0}

    placeholder_progress_bar.empty()
    return dict_data_forecast_spot
