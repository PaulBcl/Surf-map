#!/usr/bin/env python
# coding: utf-8

# ### Fonction de geocoding

# Source : https://www.shanelynn.ie/batch-geocoding-in-python-with-google-geocoding-api/

# In[2]:

import requests
import config_google
import config_michelin

#Récupère les coordonnées GPS de deux destinations grâce à l'API Google API &
#retourne l'URL qui permet d'appeler l'API Michelin
def url_builder(debut, fin, gmaps_api_key, key_michelin):
    results_debut = config_google.get_google_results(debut, api_key = gmaps_api_key)
    results_fin = config_google.get_google_results(fin, api_key = gmaps_api_key)
    lon_debut, lat_debut = str(results_debut['longitude']), str(results_debut['latitude'])
    lon_fin, lat_fin = str(results_fin['longitude']), str(results_fin['latitude'])
    url = 'https://secure-apir.viamichelin.com/apir/1/route.xml/fra?steps=1:e:' + lon_debut + ':' + lat_debut + ';1:e:' + lon_fin + ':' + lat_fin + '&authkey=' + key_michelin
    return url

# A partir d'une liste de résultats Google (fonction google_results),
# retourne la liste des positions GPS des adresses recherchées
def df_geocoding(df_addresses):
    df_geocoded = []
    for address in df_addresses:
        df_geocoded.append([address['latitude'], address['longitude']])
    return df_geocoded

# Fonction de distance & de temps
def get_distance(debut, fin, gmaps_api_key):
    url_request = url_builder(debut, fin)
    michelin_result = config_michelin.get_michelin_results(url_request)
    drivingDist = float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['drivingDist'][0]['_text'])/1000
    return drivingDist

def get_temps_parcours(debut, fin, gmaps_api_key):
    url_request = url_builder(debut, fin)
    michelin_result = config_michelin.get_michelin_results(url_request)
    drivingTime = round(float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['drivingTime'][0]['_text'])/3600, 2)
    return drivingTime

def get_prix_peage(debut, fin, gmaps_api_key):
    url_request = url_builder(debut, fin)
    michelin_result = config_michelin.get_michelin_results(url_request)
    tollCost = float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['tollCost'][0]['car'][0]['_text'])/100
    return tollCost

def get_prix_essence(debut, fin, gmaps_api_key,
                    consommation_moyenne = 6.5, prix_essence = 1.5):
    drivingDist = config_michelin.get_distance(debut, fin)
    volume_essence = drivingDist*consommation_moyenne/100
    gazPrice = round(volume_essence * prix_essence, 2)
    return gazPrice

# API Mappy
def get_road_info(debut, fin, gmaps_api_key,
                  consommation_moyenne = 6.5, prix_essence = 1.5):
    result = dict()
    url_request = url_builder(debut, fin, gmaps_api_key)
    michelin_result = config_michelin.get_michelin_results(url_request)
    result['drivingDist'] = float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['drivingDist'][0]['_text'])/1000
    result['drivingTime'] = round(float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['drivingTime'][0]['_text'])/3600, 2)
    result['tollCost'] = float(michelin_result['response']['iti'][0]['header'][0]['summaries'][0]['summary'][0]['tollCost'][0]['car'][0]['_text'])/100
    volume_essence = result['drivingDist']*consommation_moyenne/100
    result['gazPrice'] = round(volume_essence * prix_essence, 2)
    return result
