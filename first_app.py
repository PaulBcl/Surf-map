import streamlit as st
import numpy as np
import pandas as pd
import time
import gmaps
import gmaps.datasets
import pandas as pd
import logging
import urllib.request as ulib
import time
from datetime import datetime
import json
#Carte
import folium
from folium.plugins import MarkerCluster, MiniMap, Draw, Fullscreen
from folium.features import CustomIcon
#Streamlit custom
import SessionState
from streamlit_folium import folium_static #https://github.com/randyzwitch/streamlit-folium
#from st_annotated_text import annotated_text #https://github.com/tvst/st-annotated-text
#Config perso
from surfmap_config import surfmap_config



st.title('Surfmap')
base_position = [48.8434864, 2.3859893]

#Sidebar
st.sidebar.write("Les champs ci-dessous vous permettent de définir votre recherche")
label_address = "Renseignez votre adresse/ville"
address = st.sidebar.text_input(label_address, value = '',
                                max_chars = None, key = None, type = 'default', help = None)

#dfSpots = surfmap_config.dfSpots
url_database = "surfmap_config/surfspots.xlsx"
dfSpots = pd.read_excel(url_database)

def main():

    st.write("Bienvenue dans l'application Surfmap!")
    st.write("Cette application a pour but de vous aider à identifier le meilleur spot de surf accessible depuis votre adresse/ville de base à partir (i) du prix, (ii) de la distance et (iii) des conditions de surf.")

    couleur_radio_expander = st.beta_expander("Choisir le code couleur (optionnel)")
    with couleur_radio_expander:
        label_radio_choix_couleur = "Vous pouvez choisir ci-dessous un code couleur pour faciliter l'identification des spots en fonction de vos critères (distance par défaut)"
        list_radio_choix_couleur = ["Distance", "Prix"]
        checkbox_choix_couleur = st.selectbox(label_radio_choix_couleur, list_radio_choix_couleur)

    st.write("\n")
    # Sliders
    label_checkbox = "Filtres avancés"
    #checkbox = st.sidebar.checkbox(label_checkbox)
    option_prix = 0
    option_distance_h = 0
    is_option_prix_ok = False
    is_option_distance_h_ok = False
    session = SessionState.get(run_id = 0)

    #if checkbox:
    label_sidebar_options = "Options avancées"
    with st.sidebar.beta_expander(label_sidebar_options):
        label_raz = "Remise à zéro"
        col1, col2, col3 = st.beta_columns([1, 2, 1])
        with col1:
            pass
        with col2:
            raz_button = st.button(label_raz, key = None, help = "Remettre les options à zéro")
        with col3:
            pass

        if raz_button:
            session.run_id += 1
            option_prix = 0
            option_distance_h = 0

        option_prix = st.slider("Prix maximum souhaité (€, pour un aller)",
                                min_value = 0, max_value = 200,
                                key = session.run_id,
                                help = "En définissant le prix à 0€, tous les résultats s'affichent")
        option_distance_h = st.slider("Temps de conduite souhaité (heures)",
                                      min_value = 0, max_value = 15,
                                      key = session.run_id,
                                      help = "En définissant le temps maximal de conduite à 0h, tous les résultats s'affichent")

    st.sidebar.write("\n")
    #On met le boutton servant à chercher les résultats
    label_button = "Soumettre l'adresse"
    col1, col2, col3 = st.sidebar.beta_columns([1, 3.5, 1])
    with col1:
        pass
    with col2:
        validation_button = st.button(label_button, key = None, help = None)
    with col3:
        pass

    if address != '':
        if validation_button or option_prix >= 0 or option_distance_h >= 0:
            dict_data_from_address = surfmap_config.get_surfspot_data(address, dfSpots,
                                                                      surfmap_config.gmaps_api_key, surfmap_config.key_michelin)
            dfData = pd.DataFrame.from_dict(dict_data_from_address, orient = 'index').reset_index()
            dfData.rename(columns = {'index': 'nomSpot'}, inplace = True)
            dfData['latitude'] = [x[0] for x in dfData['gps']]
            dfData['longitude'] = [x[-1] for x in dfData['gps']]

            geocode_address = surfmap_config.get_google_results(address, api_key = surfmap_config.gmaps_api_key, return_full_response = True)
            if len(dfData) > 0:
                geocode_gps = [(geocode_address['latitude'] + min(dfData['latitude']))/2,
                               (geocode_address['longitude'] + min(dfData['longitude']))/2]
            else:
                geocode_gps = [geocode_address['latitude'], geocode_address['longitude']]
            #Display maps
            m = folium.Map(location = geocode_gps,
                           zoom_start = 6)
            #Petits ajouts
            marker_cluster = MarkerCluster().add_to(m)
            minimap = MiniMap(toggle_display = True)
            draw = Draw()
            folium.Marker(location = [geocode_address['latitude'], geocode_address['longitude']],
                          popup = 'Maison',
                          icon = folium.Icon(color = 'blue', icon = 'home')).add_to(m)
            minimap.add_to(m)
            draw.add_to(m)

            if option_prix > 0:
                dfData = dfData[dfData['prix'] <= option_prix]
                is_option_prix_ok = True

            if option_distance_h > 0:
                dfData = dfData[dfData['drivingTime'] <= option_distance_h]
                is_option_distance_h_ok = True

            for nomSpot in dfData['nomSpot'].tolist():
                spot_infos = dict_data_from_address[nomSpot]
                #if option_prix > 0 or option_distance_h > 0:
                #    colorIcon = surfmap_config.color_rating_criteria(is_option_prix_ok, is_option_distance_h_ok)
                #else:
                if checkbox_choix_couleur == "Prix":
                    colorIcon = surfmap_config.color_rating_prix(spot_infos['prix'])
                else:
                    colorIcon = surfmap_config.color_rating_distance(spot_infos['drivingTime'])
                marker = folium.Marker(location = spot_infos['gps'],
                                       popup = 'Spot : ' + nomSpot + ', dist : ' + str(spot_infos['drivingDist']) + ' km, temps : '
                                                           + str(spot_infos['drivingTime']) + ' h, prix : '
                                                           + str(spot_infos['tollCost'] + spot_infos['gazPrice']) + ' €, note : ',
                                       icon = folium.Icon(color = colorIcon, icon = ''))
                marker.add_to(m)

            if len(dfData) > 0:
                st.sidebar.success("Recherche terminée (" + str(len(dfData)) + " résultats) !")
            if len(dfData) == 0:
                m = folium.Map(location = base_position,
                               zoom_start = 6)
                st.sidebar.error("Aucun résultat trouvé")
    else:
        m = folium.Map(location = base_position,
                       zoom_start = 6)
        st.warning('Aucune adresse de sélectionné')

    folium_static(m)

###

main()

#Tracer
