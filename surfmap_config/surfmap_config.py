#!/usr/bin/env python
# coding: utf-8

import gmaps
import gmaps.datasets
import pandas as pd
import logging
import requests
import time
from datetime import datetime
import json
import streamlit as st

from surfmap_config import api_config

#Variables
consommation_moyenne = 6.5
prix_essence = 1.5


## Fonction permettant, à partir d'un spot de surf, de recueillir les informations de latitude et longitude
def get_google_data_gps_villeSpot(villeSpot, key_api_gmaps):
    try:
        google_api_result = api_config.get_google_results(villeSpot, key_api_gmaps)
        lon_spot = google_api_result['longitude']
        lat_spot = google_api_result['latitude']
        gps_villeSpot = (float(lat_spot), float(lon_spot))  # Return as tuple with float values
    except Exception as e:
        print('Impossible de requêter via API (Google) le spot ' + str(villeSpot))
        print(e)
        gps_villeSpot = (0.0, 0.0)  # Return as tuple with float values

    return gps_villeSpot

@st.cache_data
def load_spots(url_database):
    dfSpots = pd.read_excel(url_database)
    return dfSpots

def load_data(dfSpots, key_api_gmaps):
    dfData = dfSpots.copy(deep = True) #le dataframe comprends les colonnes du fichier Excel
    dfData['villeOrigine'] = None
    dfData['gpsVilleOrigine'] = None
    dfData['drivingDist'] = None
    dfData['drivingTime'] = None
    dfData['tollCost'] = None
    dfData['gazPrice'] = None
    dfData['prix'] = None
    #On peuple les données GPS des spots avec la fonction get_google_data_gps_villeSpot (format "[latitude, longitude]")

    if 'gpsSpot' in list(dfData.columns):
        # Convert existing gpsSpot column to tuples if needed
        dfData['gpsSpot'] = dfData['gpsSpot'].apply(
            lambda x: tuple(float(coord) for coord in x) if isinstance(x, (list, tuple)) else x
        )
    else:
        try:
            # Get GPS coordinates and convert to tuples for hashability
            dfData['gpsSpot'] = dfData.apply(lambda x: get_google_data_gps_villeSpot(x['villeSpot'], key_api_gmaps), axis=1)
            dfData['latitudeSpot'] = dfData['gpsSpot'].apply(lambda x: float(x[0]))
            dfData['longitudeSpot'] = dfData['gpsSpot'].apply(lambda x: float(x[1]))
        except Exception as e:
            print("Le chargement des données GPS des spots n'a pas fonctionné due to :")
            print(e)

    return dfData
