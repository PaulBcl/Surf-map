#!/usr/bin/env python
# coding: utf-8

# # MVP Surfmap

# In[5]:


# Google Maps (déchifrer les adresses + afficher carte)
# Calcul distance
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


# ## Attributs Google Maps

# In[107]:


gmaps_api_key = "AIzaSyCsatj1b8xHi625WNn2ex5UwtXrePOSRVM"
key_michelin = 'RESTGP20210404231529119266955396'
gmaps.configure(api_key = gmaps_api_key)

# In[85]:


consommation_moyenne = 6.5
prix_essence = 1.5


# ## Fonctions Gmaps

# In[36]:

@st.cache(suppress_st_warning = True)
def get_google_results(address, api_key = None, return_full_response = False):
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
        if api_key is not None:
            geocode_url = geocode_url + "&key={}".format(api_key)
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
        print("Couldn't find Google results")
        print(e)
    return output


# In[37]:


def get_google_distance(address1, address2, api_key = None):
    """
    Get distance between 2 positition from Google Maps Geocoding API.

    @param address1 List containing longitude & latitude of the address #1
    @param address2 List containing longitude & latitude of the address #2
    @param api_key: String API key if present from google.
    """
    try:
        now = datetime.now()
        direction_results = gmaps.directions([address1[0] + "," + address1[1]], [address2[0] + "," + address2[1]],
                                mode = 'driving')
    except Exception as e:
        print("Couldn't get Google distance")
        print(e)
    return direction_results


# In[38]:


"""
Get geocode (comme get_google_results) à partir de toutes les adresses d'un df (et gère les erreurs)
@output : dataframe contenant les geocoding

@param df_to_search : Dataframe contenant les adresses sur lesquelles faire tourner la fonction de geocoding
@param gmaps_api_key : API key Google Maps
"""
def google_results(df_to_search, gmaps_api_key = 'None'):
    df_google_results = []
    for address in df_to_search:
        try:
            geocode_result = get_google_results(address, api_key = gmaps_api_key,
                                                return_full_response = True)
            df_google_results.append(geocode_result)
        except Exception as e:
            logger.exception(e)
            logger.error("Major error while searching Google results with {}".format(address))
    return df_google_results


# In[39]:


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

# In[94]:


"""
Récupère les coordonnées GPS de deux destinations grâce à l'API Google API
@output: URL qui permet d'appeler l'API Michelin

@param start_address : adresse de départ
@param arrival_address : adresse d'arrivée
@param gmaps_api_key : API key Google Maps
"""
def url_builder(start_address, arrival_address, gmaps_api_key, key_michelin):
    try:
        results_debut = get_google_results(start_address, api_key = gmaps_api_key)
        results_fin = get_google_results(arrival_address, api_key = gmaps_api_key)
        lon_debut, lat_debut = str(results_debut['longitude']), str(results_debut['latitude'])
        lon_fin, lat_fin = str(results_fin['longitude']), str(results_fin['latitude'])
        url = 'https://secure-apir.viamichelin.com/apir/1/route.xml/fra?steps=1:e:' + lon_debut + ':' + lat_debut + ';1:e:' + lon_fin + ':' + lat_fin + '&authkey=' + key_michelin
    except Exception as e:
        print("Couldn't build the URL to request Michelin API")
    return url


# In[41]:


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


# In[42]:


"""
Appelle l'API Michelin
@output: json de l'API Michelin

@param url : url permettant d'appeler l'API michelin (fonction url_builder)
"""
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

# In[100]:


"""
Utilise l'appel à l'API michelin pour pouvoir récupérer les informations de route
@output: json de l'API Michelin

@param michelin_results : json résultat d'un appel à l'API Michelin entre une adresse A et une adresse B
"""
def get_road_info(start_address, arrival_address,
                  gmaps_api_key = 'None', key_michelin = 'None',
                  consommation_moyenne = 6.5, prix_essence = 1.5):
    result = dict()
    try:
        #On fait appel à l'API Michelin
        url_request = url_builder(start_address, arrival_address, gmaps_api_key, key_michelin)

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
        print("Impossible de récupérer les informations de la route")
        print(e)
    return result


# ## Données

# In[101]:


"""
Etant donné que les noms des spots diffèrent entre les différentes API,
il faut créer une table de correspondance pour les différents spots afin de pouvoir requêter
avec la bonne information les différents services

dataSpots = [
    ('La Torche', 'Plomeur', 'Pointdela-Torche'),
    ('Siouville / Dielette left', 'Siouville', 'Siouville'),
    ('Anael', 'Saint-Pabu', 'Anael'),
    ('Anse de Vauville', 'Beaumont-Hague', 'Ansede-Vauville'),
    ('Etretat', 'Etretat', 'Etretat'),
    ('Le Havre', 'Le Havre', 'Le-Havre-Beach'),
    ('Les Dunes', "Les Sables-d'Olone", 'Les-Dunes'),
    ('Saint Gilles Croix de Vie', 'Saint Gilles Croix de Vie', 'Saint-Gilles-Croixde-Vie'),
    ('Bud bud', 'Longevilles-sur-mer', 'Bud-bud'),
]

#On met en forme les données sous la forme d'un dataFrame
dfSpots = pd.DataFrame(dataSpots, columns = ['nomSpot', 'villeSpot', 'nomSurfForecast'])
"""

"""
Permet de récupérer les informations de route associées à des surfspots pour les afficher sur la carte
@output: un dictionnaire des coordonnées GPS (longitude, lagitude) exploitable par Folium pour afficher les données

@param dfSpots : tableau contenant nom des spots, ville des spots et nom du spot sur surf-forecast.com
"""
@st.cache(suppress_st_warning = True)
def get_surfspot_data(start_address, dfSpots,
                      gmaps_api_key = 'None', key_michelin = 'None',
                      consommation_moyenne = 6.5, prix_essence = 1.5):
    #On prends la liste des spots à requêter
    liste_surf_spots = dfSpots['nomSpot'].tolist()
    result = dict()
    for spot in liste_surf_spots:
        try:
            villeSpot = dfSpots[dfSpots['nomSpot'] == spot]['villeSpot'].tolist()[0]
            paysSpot = dfSpots[dfSpots['nomSpot'] == spot]['paysSpot'].tolist()[0]
        except:
            print('Impossible de trouver le spot ' + spot + ' dans la table de référencement')
            pass
        try:
            result[spot] = get_road_info(start_address, villeSpot,
                                         gmaps_api_key, key_michelin,
                                         consommation_moyenne, prix_essence)
            result[spot]['prix'] = result[spot]['tollCost'] + result[spot]['gazPrice']
            result[spot]['paysSpot'] = paysSpot
        except:
            print('Impossible de requêter via API (Michelin) le spot ' + str(spot))
            pass
        try:
            google_result = get_google_results(villeSpot, api_key = gmaps_api_key)
            lon_spot = google_result['longitude']
            lat_spot = google_result['latitude']
            result[spot]['gps'] = [lat_spot, lon_spot]
        except Exception as e:
            print('Impossible de requêter via API (Google) le spot ' + str(spot))
            print(e)
            pass
    return result

"""
return the color following selected criteria

@param: rating ou distance
"""
def color_rating_distance(distance_h):
    if distance_h >=8:
        return 'lightgray'
    if distance_h < 4:
        return 'green'
    if distance_h < 6:
        return 'orange'
    if distance_h < 8:
        return 'red'

def color_rating_prix(prix):
    if prix >=100:
        return 'lightgray'
    if prix < 40:
        return 'green'
    if prix < 70:
        return 'orange'
    if prix < 100:
        return 'red'

def color_rating_criteria(is_option_prix_ok, is_option_distance_h_ok):
    if is_option_prix_ok == True & is_option_distance_h_ok == True:
        return "green"
    if is_option_prix_ok == True or is_option_distance_h_ok == True:
        return "orange"
    if is_option_prix_ok == False & is_option_distance_h_ok == False:
        return "red"
