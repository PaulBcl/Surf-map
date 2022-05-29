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

#import des bibliothèques
from surfmap_config import api_config

#@st.cache(suppress_st_warning = True)
def add_new_spot_to_dfData(villeSearch, dfData,
                           key_api_gmaps, key_api_michelin):

    dfData_temp = dfData.drop_duplicates(['nomSpot', 'villeSpot']) #on se fait un dataframe avec uniquement les spots et on réinitialise les autres informations

    dfData_temp['villeOrigine'] = villeSearch #permet d'afficher la ville requêtée pour des recherches ultérieures
    #On récupère les infos GPS de la villeSpot

    google_information_villeSearch = api_config.get_google_results(villeSearch, api_config.gmaps_api_key)
    gps_data_villeSearch = [[google_information_villeSearch['latitude'], google_information_villeSearch['longitude']]] #stocke les coordonnées GPS
    dfData_temp['gpsVilleOrigine'] = gps_data_villeSearch*len(dfData_temp)

    dfData_request_michelin = dfData_temp[['gpsSpot', 'gpsVilleOrigine']]
    for row in dfData_request_michelin.itertuples():
        list_gps_coordinates = list(row) #donne une liste du type [index, gpsSpot, gpsVilleOrigine]
        try:
            michelin_information_villeSearch = api_config.get_road_info_avec_infos(list_gps_coordinates[2], list_gps_coordinates[1],
                                                                                   key_api_michelin)
            dfData_temp.loc[list_gps_coordinates[0], 'drivingDist'] = michelin_information_villeSearch['drivingDist']
            dfData_temp.loc[list_gps_coordinates[0], 'drivingTime'] = michelin_information_villeSearch['drivingTime']
            dfData_temp.loc[list_gps_coordinates[0], 'tollCost'] = michelin_information_villeSearch['tollCost']
            dfData_temp.loc[list_gps_coordinates[0], 'gazPrice'] = michelin_information_villeSearch['gazPrice']
        except Exception as e:
            print("Soucis de requêtage de l'API Michelin sur ")
            print(dfData_temp.iloc[list_gps_coordinates[0]])
            dfData_temp.loc[list_gps_coordinates[0], 'drivingDist'] = None
            dfData_temp.loc[list_gps_coordinates[0], 'drivingTime'] = None
            dfData_temp.loc[list_gps_coordinates[0], 'tollCost'] = None
            dfData_temp.loc[list_gps_coordinates[0], 'gazPrice'] = None
            pass

    dfData_temp['prix'] = dfData_temp['tollCost'] + dfData_temp['gazPrice']
    #dfData_temp['gpsSpot'] = pas besoin de réinitialiser
    #dfData_temp['latitudeSpot'] = [x[0] for x in dfData['gpsSpot']]
    #dfData_temp['longitudeSpot'] = [x[-1] for x in dfData['gpsSpot']]

    dfData_temp.to_excel("data_temp finalisé.xlsx")

    return dfData_temp #que l'on peut ajouter au dfData global !


###################################################################
#@st.cache(suppress_st_warning = True)
def get_surfspot_data(start_address, spot, dfSpots,
                      key_api_gmaps, key_api_michelin,
                      consommation_moyenne = 6.5, prix_essence = 1.5):

    try:
        villeSpot = dfSpots[dfSpots['nomSpot'] == spot]['villeSpot'].tolist()[0]
        paysSpot = dfSpots[dfSpots['nomSpot'] == spot]['paysSpot'].tolist()[0]
        nomSurfForecast = dfSpots[dfSpots['nomSpot'] == spot]['nomSurfForecast'].tolist()[0]
    except:
        print('Impossible de trouver le spot ' + spot + ' dans la table de référencement')
        pass
    try:
        result_spot = get_road_info(start_address, villeSpot,
                                     key_api_gmaps, key_api_michelin,
                                     consommation_moyenne, prix_essence)
        result_spot['prix'] = result_spot['tollCost'] + result_spot['gazPrice']
        result_spot['paysSpot'] = paysSpot
        result_spot['nomSurfForecast'] = nomSurfForecast
    except Exception as e:
        print(e)
        print('Impossible de requêter via API (Michelin) le spot ' + str(spot))
        pass

    return result_spot


# ## Données
"""
Permet de récupérer les informations de route associées à des surfspots pour les afficher sur la carte
@output: un dictionnaire des coordonnées GPS (longitude, lagitude) exploitable par Folium pour afficher les données

@param dfSpots : tableau contenant nom des spots, ville des spots et nom du spot sur surf-forecast.com
"""
#@st.cache(suppress_st_warning = True)
def load_surfspot_data(start_address, dfSpots,
                      key_api_gmaps, key_api_michelin,
                      consommation_moyenne = 6.5, prix_essence = 1.5):
    #On affiche la barre de chargement
    placeholder_progress_bar = st.empty()
    progress_bar = placeholder_progress_bar.progress(0)
    nb_percent_complete = int(100/len(dfSpots))
    iteration = 0

    #On prends la liste des spots à requêter
    liste_surf_spots = dfSpots['nomSpot'].tolist()

    result = dict()

    for spot in liste_surf_spots:
        iteration += 1

        result[spot] = get_surfspot_data(start_address, spot, dfSpots,
                              key_api_gmaps, key_api_michelin,
                              consommation_moyenne = 6.5, prix_essence = 1.5)

        progress_bar.progress(nb_percent_complete*iteration + 1)

    placeholder_progress_bar.empty()

    return result
