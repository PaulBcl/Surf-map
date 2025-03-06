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
from tqdm import tqdm, tqdm_notebook
import streamlit as st

# Get API key from Streamlit secrets
gmaps_api_key = st.secrets["google_maps_api_key"]
gmaps.configure(api_key = gmaps_api_key)

#Variables
consommation_moyenne = 6.5  # L/100km
prix_essence = 1.5  # €/L
toll_cost_per_km = 0.05  # €/km (average toll cost in France)

#data
url_database = "surfmap_config/surfspots.xlsx"

@st.cache_data
def get_google_results(address, key_api_gmaps, return_full_response = False):
    """
    Get geocode results from Google Maps Geocoding API.
    """
    try:
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json?address={}".format(address)
        if key_api_gmaps is not None:
            geocode_url = geocode_url + "&key={}".format(key_api_gmaps)
        results = requests.get(geocode_url)
        results = results.json()

        if len(results['results']) == 0:
            output = {
                "formatted_address" : None,
                "latitude": None,
                "longitude": None,
                "accuracy": None,
                "google_place_id": None,
                "type": None,
                "postcode": None
            }
        else:
            answer = results['results'][0]
            output = {
                "formatted_address" : answer.get('formatted_address'),
                "latitude": answer.get('geometry').get('location').get('lat'),
                "longitude": answer.get('geometry').get('location').get('lng'),
                "accuracy": answer.get('geometry').get('location_type'),
                "google_place_id": answer.get("place_id"),
                "type": ",".join(answer.get('types')),
                "postcode": ",".join([x['long_name'] for x in answer.get('address_components')
                                      if 'postal_code' in x.get('types')])
            }

        output['input_string'] = address
        output['number_of_results'] = len(results['results'])
        output['status'] = results.get('status')
        if return_full_response is True:
            output['response'] = results
    except Exception as e:
        print("Couldn't find Google results on address : " + str(address))
        print(e)
    return output

@st.cache_data
def get_google_route_info(start_coords, end_coords, key_api_gmaps):
    """
    Get route information using Google Maps Directions API.
    
    @param start_coords: List [lat, lng] of starting point
    @param end_coords: List [lat, lng] of ending point
    @param key_api_gmaps: Google Maps API key
    """
    try:
        # Format coordinates for Google Maps API
        origin = f"{start_coords[0]},{start_coords[1]}"
        destination = f"{end_coords[0]},{end_coords[1]}"
        
        # Get directions from Google Maps
        directions = gmaps.directions(origin, destination, mode='driving')
        
        if not directions:
            return None
            
        route = directions[0]
        leg = route['legs'][0]
        
        # Extract route information
        distance = leg['distance']['value'] / 1000  # Convert to km
        duration = leg['duration']['value'] / 3600  # Convert to hours
        
        # Calculate costs
        fuel_cost = (distance * consommation_moyenne / 100) * prix_essence  # Fuel cost in €
        toll_cost = distance * toll_cost_per_km  # Estimated toll cost in €
        
        return {
            'distance': round(distance, 1),
            'duration': round(duration, 2),
            'toll_cost': round(toll_cost, 2),
            'fuel_cost': round(fuel_cost, 2)
        }
    except Exception as e:
        print(f"Error getting route information: {str(e)}")
        return None

@st.cache_data
def get_route_info(start_address, end_address, key_api_gmaps):
    """
    Get route information using addresses.
    """
    try:
        # Get coordinates for both addresses
        start_results = get_google_results(start_address, key_api_gmaps)
        end_results = get_google_results(end_address, key_api_gmaps)
        
        if not start_results['latitude'] or not end_results['latitude']:
            return None
            
        # Get route information using coordinates
        return get_google_route_info(
            [start_results['latitude'], start_results['longitude']],
            [end_results['latitude'], end_results['longitude']],
            key_api_gmaps
        )
    except Exception as e:
        print(f"Error in get_route_info: {str(e)}")
        return None

@st.cache_data
def google_results(df_to_search, key_api_gmaps):
    df_google_results = []
    for address in df_to_search:
        try:
            geocode_result = get_google_results(address, key_api_gmaps,
                                                return_full_response = True)
            df_google_results.append(geocode_result)
        except Exception as e:
            logging.exception(e)
            logging.error("Major error while searching Google results with {}".format(address))
    return df_google_results

@st.cache_data
def df_geocoding(df_adresses):
    try:
        df_geocoded = []
        for address in df_adresses:
            df_geocoded.append([address['latitude'], address['longitude']])
    except Exception as e:
        print("Couldn't geocode adresses in the dataframe")
        print(e)
    return df_geocoded
