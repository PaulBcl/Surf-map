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

@st.cache_data
def add_new_spot_to_dfData(villeSearch, dfData, key_api_gmaps):
    dfData_temp = dfData.drop_duplicates(['nomSpot', 'villeSpot'])

    dfData_temp['villeOrigine'] = villeSearch

    # Get GPS coordinates for the search city
    google_information_villeSearch = api_config.get_google_results(villeSearch, key_api_gmaps)
    if google_information_villeSearch['latitude'] is not None and google_information_villeSearch['longitude'] is not None:
        # Convert coordinates to tuple for hashability
        gps_data_villeSearch = (google_information_villeSearch['latitude'], google_information_villeSearch['longitude'])
        dfData_temp['gpsVilleOrigine'] = [gps_data_villeSearch] * len(dfData_temp)
    else:
        st.error(f"Could not get GPS coordinates for {villeSearch}")
        return None

    # Get route information using Google Maps API
    dfData_request = dfData_temp[['gpsSpot', 'gpsVilleOrigine']]
    for row in dfData_request.itertuples():
        list_gps_coordinates = list(row)
        try:
            # Convert coordinates to lists for API call
            origin = list(list_gps_coordinates[2])  # Convert tuple to list
            destination = list(list_gps_coordinates[1])  # Convert tuple to list
            
            route_info = api_config.get_google_route_info(
                origin,  # origin
                destination,  # destination
                key_api_gmaps
            )
            if route_info:
                dfData_temp.loc[list_gps_coordinates[0], 'drivingDist'] = route_info['distance']
                dfData_temp.loc[list_gps_coordinates[0], 'drivingTime'] = route_info['duration']
                dfData_temp.loc[list_gps_coordinates[0], 'tollCost'] = route_info.get('toll_cost', 0)
                dfData_temp.loc[list_gps_coordinates[0], 'gazPrice'] = route_info.get('fuel_cost', 0)
        except Exception as e:
            st.write(f"Error getting route information for spot: {str(e)}")
            dfData_temp.loc[list_gps_coordinates[0], 'drivingDist'] = None
            dfData_temp.loc[list_gps_coordinates[0], 'drivingTime'] = None
            dfData_temp.loc[list_gps_coordinates[0], 'tollCost'] = None
            dfData_temp.loc[list_gps_coordinates[0], 'gazPrice'] = None
            continue

    dfData_temp['prix'] = dfData_temp['tollCost'] + dfData_temp['gazPrice']

    return dfData_temp

@st.cache_data
def get_surfspot_data(start_address, spot, dfSpots, key_api_gmaps):
    try:
        villeSpot = dfSpots[dfSpots['nomSpot'] == spot]['villeSpot'].tolist()[0]
        paysSpot = dfSpots[dfSpots['nomSpot'] == spot]['paysSpot'].tolist()[0]
        nomSurfForecast = dfSpots[dfSpots['nomSpot'] == spot]['nomSurfForecast'].tolist()[0]
    except:
        st.error(f'Impossible de trouver le spot {spot} dans la table de référencement')
        return None

    try:
        route_info = api_config.get_google_route_info(start_address, villeSpot, key_api_gmaps)
        if route_info:
            result_spot = {
                'drivingDist': route_info['distance'],
                'drivingTime': route_info['duration'],
                'tollCost': route_info.get('toll_cost', 0),
                'gazPrice': route_info.get('fuel_cost', 0),
                'prix': route_info.get('toll_cost', 0) + route_info.get('fuel_cost', 0),
                'paysSpot': paysSpot,
                'nomSurfForecast': nomSurfForecast
            }
        else:
            st.warning(f'Impossible de calculer l\'itinéraire pour le spot {spot}')
            return None
    except Exception as e:
        st.error(f"Error processing spot {spot}: {str(e)}")
        return None

    return result_spot

@st.cache_data
def load_surfspot_data(start_address, dfSpots, key_api_gmaps):
    placeholder_progress_bar = st.empty()
    progress_bar = placeholder_progress_bar.progress(0)
    nb_percent_complete = int(100/len(dfSpots))
    iteration = 0

    liste_surf_spots = dfSpots['nomSpot'].tolist()
    result = dict()

    for spot in liste_surf_spots:
        iteration += 1
        result[spot] = get_surfspot_data(start_address, spot, dfSpots, key_api_gmaps)
        progress_bar.progress(nb_percent_complete*iteration + 1)

    placeholder_progress_bar.empty()
    return result
