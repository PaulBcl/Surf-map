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
    pageSurfReport = requests.get(urlSurfReport)
    contentPage = pageSurfReport.content
    soupContentPage = BeautifulSoup(contentPage, features = "html.parser")
    return soupContentPage

@st.cache(suppress_st_warning = True)
def get_dayList_forecast():
    """
    On récupère les jours qui font l'objet de prévision puis on les met en forme
    Le résultat est tel : dayList = ['Vendredi 03', 'Samedi 04', 'Dimanche 05', 'Lundi 06', 'Mardi 07', 'Mercredi 08', 'Jeudi 09', 'Ven 10']

    @param N/A doit être appelée en daily
    """
    soupContentPage = get_surfSpot_url("La-Ciotat")
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

@st.cache(suppress_st_warning = True)
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

        #On récupère le tableau des prévisions
        table = soupContentPage.find_all("tbody", {"class": "forecast-table__basic"})

        #On récupère ensuite toutes les notations que l'on met en forme
        #Le résultat est tel : noteList = [0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 2]
        resultNotations = soupContentPage.find_all("tr", {"class": "forecast-table__row forecast-table-rating"})[0].find_all("img")
        noteList = []
        for resultNotation in resultNotations:
            note = int(resultNotation['alt'])
            noteList.append(note)

        #On agrège ensuite les résultats sous forme d'un dictionnaire
        #Ce dictionnaire contient pour chaque jour de dayList la moyenne des notations du jour
        #Le résultat est tel : dict_data_spot = {'Vendredi 03': 1.3333333333333333, ...,  'Ven 10': 3.0}
        index_average = 0
        for day in dayList:
            dict_data_spot[day] = round(np.average(noteList[index_average:index_average+3]), 2)
            index_average += 3

    except Exception as e:
        print(e)
        print("Pas d'informations surf-report sur " + str(nomSurfForecast))
        dict_data_spot['No day'] = 0.0
    return dict_data_spot
