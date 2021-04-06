#!/usr/bin/env python
# coding: utf-8

# ### Fonction de geocoding

# Source : https://www.shanelynn.ie/batch-geocoding-in-python-with-google-geocoding-api/

# In[2]:

import pandas as pd
from .surfmap_config import config_surfmap_function
from .surfmap_config import config_google
gmaps_api_key = "AIzaSyCsatj1b8xHi625WNn2ex5UwtXrePOSRVM"
key_michelin = 'RESTGP20210404231529119266955396'

dataSpots = [
    ('La Torche', 'Plomeur', 'Pointdela-Torche'),
    ('Siouville / Dielette left', 'Siouville', 'Siouville'),
    ('Anael', 'Saint-Pabu', 'Anael'),
    ('Anse de Vauville', 'Beaumont-Hague', 'Ansede-Vauville'),
    ('Etretat', 'Etretat', 'Etretat'),
    ('Le Havre', 'Le Havre', 'Le-Havre-Beach'),
    ('Les Dunes', "Les Sables-d'Olone", 'Les-Dunes'),
    ('Saint Gilles Croix de Vie', 'Saint Gilles Croix de Vie', 'Saint-Gilles-Croixde-Vie'),
]

dfSpots = pd.DataFrame(dataSpots, columns = ['nomSpot', 'villeSpot', 'nomSurfForecast'])

dfSpots = dfSpots.append({'nomSpot': 'Bud Bud',
                          'villeSpot': 'Longevilles-sur-mer',
                          'nomSurfForecast': 'Bud-Bud'},
                          ignore_index = True)

#A partir d'une liste de surfspots, retourne un dictionnaire exploitable par Folium pour afficher les données
def get_surfspot_data(address, liste_surf_spots, dfSpots = dfSpots):
    result = dict()
    for spot in liste_surf_spots:
        try:
            villeSpot = dfSpots[dfSpots['nomSpot'] == spot]['villeSpot'].tolist()[0]
        except:
            print('Impossible de trouver le spot ' + spot + ' dans la table de référencement')
            pass
        try:
            result[spot] = config_surfmap_function.get_road_info('6 Cité Moynet, 75012 Paris', villeSpot,
                                                                 gmaps_api_key = gmaps_api_key)
        except:
            print('Impossible de requêter via API (Michelin) le spot ' + str(spot))
            pass
        try:
            google_result = config_google.get_google_results(villeSpot, api_key = gmaps_api_key)
            lon_spot = google_result['longitude']
            lat_spot = google_result['latitude']
            result[spot]['gps'] = [lat_spot, lon_spot]
        except:
            print('Impossible de requêter via API (Google) le spot ' + str(spot))
            pass
    return result
