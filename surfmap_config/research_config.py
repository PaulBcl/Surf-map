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
        # Store coordinates as a tuple for hashability
        gps_data_villeSearch = (float(google_information_villeSearch['latitude']), float(google_information_villeSearch['longitude']))
        dfData_temp['gpsVilleOrigine'] = [gps_data_villeSearch] * len(dfData_temp)
    else:
        st.error(f"Could not get GPS coordinates for {villeSearch}")
        return None

    # Convert any list coordinates to tuples for hashability
    if 'gpsSpot' in dfData_temp.columns:
        dfData_temp['gpsSpot'] = dfData_temp['gpsSpot'].apply(
            lambda x: tuple(float(coord) for coord in x) if isinstance(x, (list, tuple)) else x
        )

    # Initialize numeric columns with default values
    numeric_columns = ['drivingDist', 'drivingTime', 'tollCost', 'gazPrice', 'prix']
    for col in numeric_columns:
        dfData_temp[col] = 0.0

    # Get route information using Google Maps API
    dfData_request = dfData_temp[['gpsSpot', 'gpsVilleOrigine']]
    for row in dfData_request.itertuples():
        try:
            # Get spot coordinates and convert to float
            spot_coords = row.gpsSpot
            if isinstance(spot_coords, (list, tuple)) and len(spot_coords) == 2:
                spot_lat, spot_lon = float(spot_coords[0]), float(spot_coords[1])
            else:
                continue

            # Get origin coordinates and convert to float
            origin_coords = row.gpsVilleOrigine
            if isinstance(origin_coords, (list, tuple)) and len(origin_coords) == 2:
                origin_lat, origin_lon = float(origin_coords[0]), float(origin_coords[1])
            else:
                continue

            # Format coordinates for API call
            origin = [origin_lat, origin_lon]
            destination = [spot_lat, spot_lon]
            
            route_info = api_config.get_google_route_info(
                origin,
                destination,
                key_api_gmaps
            )
            
            if route_info:
                # Store route information as float values
                dfData_temp.loc[row.Index, 'drivingDist'] = float(route_info['distance'])
                dfData_temp.loc[row.Index, 'drivingTime'] = float(route_info['duration'])
                dfData_temp.loc[row.Index, 'tollCost'] = float(route_info.get('toll_cost', 0))
                dfData_temp.loc[row.Index, 'gazPrice'] = float(route_info.get('fuel_cost', 0))

        except Exception as e:
            continue

    # Calculate total price as sum of toll and fuel costs
    dfData_temp['prix'] = dfData_temp['tollCost'] + dfData_temp['gazPrice']

    # Ensure all numeric columns are float type
    for col in numeric_columns:
        if col in dfData_temp.columns:
            dfData_temp[col] = pd.to_numeric(dfData_temp[col], errors='coerce').fillna(0.0)

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
            return None
    except Exception as e:
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
