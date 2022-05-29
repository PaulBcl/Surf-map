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

gmaps_api_key = "AIzaSyCUV_lu8Fq10PySnL2j_00YEGWJXLfg70Q"
key_michelin = 'RESTGP20220527094740336483884311' #initiée le 27/05/2022, valable jusqu'au 11/07/2022
gmaps.configure(api_key = gmaps_api_key)

#Variables
consommation_moyenne = 6.5
prix_essence = 1.5

#data
url_database = "surfmap_config/surfspots.xlsx"

# ## Fonctions Gmaps

#@st.cache(suppress_st_warning = True)
def get_google_results(address, key_api_gmaps, return_full_response = False):
    """
    Get geocode results from Google Maps Geocoding API.

    Note, that in the case of multiple google geocode reuslts, this function returns details of the FIRST result.

    @param address: String address as accurate as possible. For Example "18 Grafton Street, Dublin, Ireland"
    @param api_key: String API key if present from google.
                    If supplied, requests will use your allowance from the Google API. If not, you
                    will be limited to the free usage of 2500 requests per day.
    @param return_full_response: Boolean to indicate if you'd like to return the full response from google. This
                    is useful if you'd like additional location details for storage or parsing later.
    """
    try:
        # Set up your Geocoding url
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json?address={}".format(address)
        if key_api_gmaps is not None:
            geocode_url = geocode_url + "&key={}".format(key_api_gmaps)
        # Ping google for the reuslts:
        results = requests.get(geocode_url)
        # Results will be in JSON format - convert to dict using requests functionality
        results = results.json()

        # if there's no results or an error, return empty results.
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

        # Append some other details:
        output['input_string'] = address
        output['number_of_results'] = len(results['results'])
        output['status'] = results.get('status')
        if return_full_response is True:
            output['response'] = results
    except Exception as e:
        print("Couldn't find Google results on address : " + str(address))
        print(e)
    return output


def get_google_distance(address1, address2, key_api_gmaps):
    """
    Get distance between 2 positition from Google Maps Geocoding API.

    @param address1 List containing longitude & latitude of the address #1
    @param address2 List containing longitude & latitude of the address #2
    @param key_api_gmaps: String API key if present from google.
    """
    try:
        now = datetime.now()
        direction_results = gmaps.directions([address1[0] + "," + address1[1]], [address2[0] + "," + address2[1]],
                                mode = 'driving')
    except Exception as e:
        print("Couldn't get Google distance")
        print(e)
    return direction_results

"""
Get geocode (comme get_google_results) à partir de toutes les adresses d'un df (et gère les erreurs)
@output : dataframe contenant les geocoding

@param df_to_search : Dataframe contenant les adresses sur lesquelles faire tourner la fonction de geocoding
@param key_api_gmaps : API key Google Maps
"""

def google_results(df_to_search, key_api_gmaps):
    df_google_results = []
    for address in df_to_search:
        try:
            geocode_result = get_google_results(address, key_api_gmaps,
                                                return_full_response = True)
            df_google_results.append(geocode_result)
        except Exception as e:
            logger.exception(e)
            logger.error("Major error while searching Google results with {}".format(address))
    return df_google_results


"""
Retourne la liste des positions GPS des adresses recherchées (lecture des json d'un appel API Google Maps)
@output: dataframe contenant les latitudes et les longitudes du Dataframe requêté

@param df_to_search : liste de json Google Maps API contenant les geocoding des adresses recherchées (utiliser la fonction google_results)
"""
# A partir d'une liste de résultats Google (fonction google_results),
# retourne la liste des positions GPS des adresses recherchées

def df_geocoding(df_adresses):
    try:
        df_geocoded = []
        for address in df_adresses:
            df_geocoded.append([address['latitude'], address['longitude']])
    except Exception as e:
        print("Couldn't geocode adresses in the dataframe")
        print(e)
    return df_geocoded


# ## Mappy/Michelin

"""
Récupère les coordonnées GPS de deux destinations grâce à l'API Google API
@output: URL qui permet d'appeler l'API Michelin

@param start_address : adresse de départ
@param arrival_address : adresse d'arrivée
@param key_api_gmaps : API key Google Maps
"""

#Version 1 : 0 info sur les latitudes & longitudes
def url_builder_no_infos(start_address, arrival_address, key_api_gmaps, key_api_michelin):
    try:
        results_debut = get_google_results(start_address, key_api_gmaps)
        results_fin = get_google_results(arrival_address, key_api_gmaps)
        lon_debut, lat_debut = str(results_debut['longitude']), str(results_debut['latitude'])
        lon_fin, lat_fin = str(results_fin['longitude']), str(results_fin['latitude'])
        url = 'https://secure-apir.viamichelin.com/apir/1/route.xml/fra?steps=1:e:' + lon_debut + ':' + lat_debut + ';1:e:' + lon_fin + ':' + lat_fin + '&authkey=' + key_api_michelin
    except Exception as e:
        print("Couldn't build the URL to request Michelin API in version 1 of urlbuilder due to : ")
        print(e)
    return url

#Version 2 : on connaît les latitudes et longitudes des spots (permets de réduire les appels à l'API Google)
def url_builder_avec_infos(gpsOrigine, gpsTarget, key_api_michelin):
    try:
        lon_debut, lat_debut = str(gpsOrigine[1]), str(gpsOrigine[0]) #stockés au format "latitude, longitude" pour faciliter la lecture folium
        lon_fin, lat_fin = str(gpsTarget[1]), str(gpsTarget[0])
        url = 'https://secure-apir.viamichelin.com/apir/1/route.xml/fra?steps=1:e:' + lon_debut + ':' + lat_debut + ';1:e:' + lon_fin + ':' + lat_fin + '&authkey=' + key_api_michelin
    except Exception as e:
        print("Couldn't build the URL to request Michelin API in version 2 of urlbuilder due to ")
        print(e)
    return url


"""
Appelle l'API Michelin
@output: json de l'API Michelin

@param url : url permettant d'appeler l'API michelin (fonction url_builder)
"""

## Fonction permettant de lire les résultats de l'API Michelin

import xml.etree.ElementTree as ET
from copy import copy

def dictify(r,root=True):
    if root:
        return {r.tag : dictify(r, False)}
    d=copy(r.attrib)
    if r.text:
        d["_text"]=r.text
    for x in r.findall("./*"):
        if x.tag not in d:
            d[x.tag]=[]
        d[x.tag].append(dictify(x,False))
    return d

# Appel à l'API Michelin

def get_michelin_results(url, header = None):
    try:
        get = requests.get(url)
        results_raw = get.text
        root = ET.fromstring(results_raw)
        results = dictify(root)
        return results
    except Exception as e:
        print("Couldn't request Michelin API")
        print(e)


# ### Création de fonction standard de requêtage de données

"""
Utilise l'appel à l'API michelin pour pouvoir récupérer les informations de route
@output: json de l'API Michelin

@param michelin_results : json résultat d'un appel à l'API Michelin entre une adresse A et une adresse B
"""
# v1 : si on a 0 infos de longitude et latitude
def get_road_info_no_infos(start_address, arrival_address,
                  key_api_gmaps, key_api_michelin,
                  consommation_moyenne = 6.5, prix_essence = 1.7):
    result = dict()
    try:
        #On fait appel à l'API Michelin
        url_request_no_infos = url_builder(start_address, arrival_address, key_api_gmaps, key_api_michelin)

        #On met en forme
        michelin_result = get_michelin_results(url_request)
        #On extrait les résultats
        result['drivingDist'] = float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['drivingDist'][0]['_text'])/1000
        result['drivingTime'] = round(float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['drivingTime'][0]['_text'])/3600, 2)
        result['tollCost'] = float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['tollCost'][0]['car'][0]['_text'])/100

        #On calcule les informations annexes
        volume_essence = result['drivingDist']*consommation_moyenne/100
        result['gazPrice'] = round(volume_essence * prix_essence, 2)
    except Exception as e:
        print("Impossible de récupérer les informations de la route sur la v1 du requêteur michelin")
        print(e)
    return result

#v2 : si on a déjà les coordonnées gpsSpot
def get_road_info_avec_infos(gpsOrigine, gpsTarget, key_api_michelin,
                             consommation_moyenne = 6.5, prix_essence = 1.7):
    result = dict()
    try:
        #On fait appel à l'API Michelin
        url_request = url_builder_avec_infos(gpsOrigine, gpsTarget, key_api_michelin)

        #On met en forme
        michelin_result = get_michelin_results(url_request)
        #On extrait les résultats
        result['drivingDist'] = float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['drivingDist'][0]['_text'])/1000
        result['drivingTime'] = round(float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['drivingTime'][0]['_text'])/3600, 2)
        result['tollCost'] = float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['tollCost'][0]['car'][0]['_text'])/100

        #On calcule les informations annexes
        volume_essence = result['drivingDist']*consommation_moyenne/100
        result['gazPrice'] = round(volume_essence * prix_essence, 2)
    except Exception as e:
        print("Impossible de récupérer les informations de la route sur la v2 (à partir des coordonnées GPS) du requêteur michelin")
        print(e)
    return result
