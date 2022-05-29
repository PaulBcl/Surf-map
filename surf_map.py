import streamlit as st
import numpy as np
import pandas as pd
import time
import gmaps
import gmaps.datasets
import pandas as pd
import logging
from datetime import datetime
import json

#Asynchronous run on api
#from https://pawelmhm.github.io/asyncio/python/aiohttp/2016/04/22/asyncio-aiohttp.html
import asyncio
from aiohttp import ClientSession
#import ray

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
from surfmap_config import forecast_config
from surfmap_config import displaymap_config
from surfmap_config import research_config
from surfmap_config import api_config
#documents d'upload : https://github.com/MaartenGr/streamlit_guide
#source : https://towardsdatascience.com/quickly-build-and-deploy-an-application-with-streamlit-988ca08c7e83

st.title('Surfmap')
base_position = [48.8434864, 2.3859893]

#Sidebar & data
label_address = "Renseignez votre ville"
address = st.sidebar.text_input(label_address, value = '',
                                max_chars = None, key = None, type = 'default', help = None)

#On peuple la base de données
url_database = "surfmap_config/surfspots.xlsx"
dfSpots = surfmap_config.load_spots(url_database)
dayList = forecast_config.get_dayList_forecast()


def main():

    dfData = surfmap_config.load_data(dfSpots, api_config.gmaps_api_key) #on pourra déplacer au sein du main pour n'initier le peuplement de la base de données que lors du premier appel de la BDD

    st.markdown("Bienvenue dans l'application :ocean: Surfmap !")
    st.markdown("Cette application a pour but de vous aider à identifier le meilleur spot de surf accessible depuis votre ville ! Bon ride :surfer:")

    st.success("New release🌴! Les conditions de surf sont désormais disponibles pour optimiser votre recherche !")

    explication_expander = st.expander("Guide d'utilisation")
    with explication_expander:
        st.write("Vous pourrez trouver ci-dessous une carte affichant les principaux spots de surf accessibles depuis votre ville. Pour cela, il suffit d'indiquer dans la barre de gauche votre position et appuyer sur 'Soumettre l'adresse'.")
        st.write("La carte qui s'affiche ci-dessous indique votre position (🏠 en bleu) ainsi que les différents spots en proposant les meilleurs spots (en vert 📗, modifiable ci-dessous dans 'code couleur') et en affichant les informations du spot lorsque vous cliquez dessus.")
        st.write("Vous pouvez affiner les spots proposés en sélectionnant les options avancées et en filtrant sur vos prérequis. Ces choix peuvent porter sur (i) le prix (💸) maximum par aller, (ii) le temps de parcours (⏳) acceptable, (iii) le pays de recherche (🇫🇷) et (iv) les conditions prévues (🏄) des spots recherchés !")

    couleur_radio_expander = st.expander("Légende de la carte")
    with couleur_radio_expander:
        #st.markdown("_Légende :_")
        st.markdown(":triangular_flag_on_post: représente un spot de surf")
        st.markdown("La couleur donne la qualité du spot à partir de vos critères : :green_book: parfait, :orange_book: moyen, :closed_book: déconseillé")
        #st.markdown("_Choisir le code couleur (optionnel) :_")
        label_radio_choix_couleur = "Vous pouvez choisir ci-dessous un code couleur pour faciliter l'identification des spots en fonction de vos critères (prévisions du spot par défaut)"
        list_radio_choix_couleur = ["🏄‍♂️ Prévisions", "🏁 Distance", "💸 Prix"]
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
    label_sidebar_profil = "Profil"
    sidebar_profil = st.sidebar.expander(label_sidebar_profil)
    with sidebar_profil:
        #st.markdown("Quel type de surfer es-tu ?")
        st.warning("Work in progress")
        label_transport = "Moyen(s) de transport(s) favori(s)"
        list_transport = ["🚗 Voiture", "🚝 Train", "🚲 Vélo", "⛵ Bateau"]
        multiselect_transport = st.multiselect(label_transport, list_transport,
                                          default = list_transport[0])

    label_sidebar_options = "Options avancées"
    sidebar_options = st.sidebar.expander(label_sidebar_options)
    with sidebar_options:
        #st.markdown("Choix des options pour l'affichage des spots")
        label_raz = "Remise à zéro"
        col1, col2, col3 = st.columns([1, 2, 1])
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

        label_daily_forecast = "Jour souhaité pour l'affichage des prévisions de surf"
        selectbox_daily_forecast = st.selectbox(label_daily_forecast, dayList)

        option_forecast = st.slider("Conditions minimum souhaitées (/10)",
                                min_value = 0, max_value = 10,
                                key = session.run_id,
                                help = "En définissant les prévisions à 0, tous les résultats s'affichent")

        option_prix = st.slider("Prix maximum souhaité (€, pour un aller)",
                                min_value = 0, max_value = 200,
                                key = session.run_id,
                                help = "En définissant le prix à 0€, tous les résultats s'affichent")
        option_distance_h = st.slider("Temps de conduite souhaité (heures)",
                                      min_value = 0, max_value = 15,
                                      key = session.run_id,
                                      help = "En définissant le temps maximal de conduite à 0h, tous les résultats s'affichent")

        label_choix_pays = "Choix des pays pour les spots à afficher"
        list_pays = ["🇫🇷 France", "🇪🇸 Espagne", "🇮🇹 Italie"]
        multiselect_pays = st.multiselect(label_choix_pays, list_pays,
                                          default = list_pays[0],
                                          key = session.run_id)

    st.sidebar.write("\n")
    #On met le boutton servant à chercher les résultats
    label_button = "Soumettre l'adresse"
    col1, col2, col3 = st.sidebar.columns([1, 3.5, 1])
    with col1:
        pass
    with col2:
        validation_button = st.button(label_button, key = None, help = None)
    with col3:
        pass

    if address != '':
        if validation_button or option_prix >= 0 or option_distance_h >= 0 or option_forecast >= 0:

            #dict_data_from_address = surfmap_config.load_surfspot_data(address, dfSpots,
            #                                                          surfmap_config.gmaps_api_key, surfmap_config.key_michelin)
            #dfData = pd.DataFrame.from_dict(dict_data_from_address, orient = 'index').reset_index()
            #dfData.rename(columns = {'index': 'nomSpot'}, inplace = True)
            #dfData['latitude'] = [x[0] for x in dfData['gps']]
            #dfData['longitude'] = [x[-1] for x in dfData['gps']]

            #geocode_address = surfmap_config.get_google_results(address, surfmap_config.gmaps_api_key, return_full_response = True)

            #Insérer ici la boucle sur le dataset global (i.e. vérification présence ville requêtée) + filtrage pour affichage dataframe
            # et remplacer ci-dessous "dfData" par "dfDataDisplay"

            #On commence par regarder si la ville recherchée a déjà été requêtée
            if address in dfData['villeOrigine'].tolist():
                dfDataDisplay = dfData[dfData['villeOrigine'] == address]
            else: #cas où la ville n'a jamais été requêtée
                dfSearchVille = research_config.add_new_spot_to_dfData(address, dfData, api_config.gmaps_api_key, api_config.key_michelin)
                dfData = pd.concat([dfData, dfSearchVille]) #appel à la fonction de merging de research_config
                dfDataDisplay = dfData[dfData['villeOrigine'] == address]

            dfDataDisplay.rename(columns = {'index': 'nomSpot'}, inplace = True)

            #if len(dfDataDisplay) > 0:

            #    geocode_gps = [(dfDataDisplay['gpsVilleOrigine'][0][0] + min(dfData['latitude']))/2,
            #                    (dfDataDisplay['gpsVilleOrigine'][0][1] + min(dfData['longitude']))/2]

            #else:

            gpsHome = [dfDataDisplay['gpsVilleOrigine'][0][0], dfDataDisplay['gpsVilleOrigine'][0][1]]

            #Display maps
            m = folium.Map(location = gpsHome,
                           zoom_start = 5)
            #Petits ajouts
            marker_cluster = MarkerCluster().add_to(m)
            minimap = MiniMap(toggle_display = True)
            draw = Draw()
            popupHome = folium.Popup("💑 Maison",
                                     max_width = '150')
            folium.Marker(location = [dfDataDisplay['gpsVilleOrigine'][0][0], dfDataDisplay['gpsVilleOrigine'][0][1]],
                          popup = popupHome,
                          icon = folium.Icon(color = 'blue', icon = 'home')).add_to(m)
            minimap.add_to(m)
            draw.add_to(m)

            #Ajout des données de forecast
            forecast_data = forecast_config.load_forecast_data(dfDataDisplay['nomSurfForecast'].tolist(), dayList)
            dfDataDisplay['forecast'] = [forecast_data[spot].get(selectbox_daily_forecast) for spot in dfDataDisplay['nomSurfForecast']]

            if option_prix > 0:
                dfDataDisplay = dfDataDisplay[dfDataDisplay['prix'] <= option_prix]
                is_option_prix_ok = True

            if option_distance_h > 0:
                dfDataDisplay = dfDataDisplay[dfDataDisplay['drivingTime'] <= option_distance_h]
                is_option_distance_h_ok = True

            if option_forecast > 0:
                dfDataDisplay = dfDataDisplay[dfDataDisplay['forecast'] >= option_forecast]

            multiselect_pays = [x.split()[-1] for x in multiselect_pays] #permet d'enlever les émoji pour la recherche
            dfDataDisplay = dfDataDisplay[dfDataDisplay['paysSpot'].isin(multiselect_pays)]

            for nomSpot in dfDataDisplay['nomSpot'].tolist():
                spot_infos_df = dfDataDisplay[dfDataDisplay['nomSpot'] == nomSpot]
                spot_infos = spot_infos_df.to_dict('records')[0]

                try:
                    spot_forecast = dfDataDisplay[dfDataDisplay['nomSpot'] == nomSpot]['forecast'].tolist()[0]
                    #if option_prix > 0 or option_distance_h > 0:
                    #    colorIcon = displaymap_config.color_rating_criteria(is_option_prix_ok, is_option_distance_h_ok)
                    #else:
                    if checkbox_choix_couleur == list_radio_choix_couleur[-1]: #corresponds à "prix" avec l'icône associée
                        colorIcon = displaymap_config.color_rating_prix(spot_infos['prix'])
                    elif checkbox_choix_couleur == list_radio_choix_couleur[0]: #corresponds à "forecast" avec l'icône associée
                        colorIcon = displaymap_config.color_rating_forecast(spot_forecast)
                    else:
                        colorIcon = displaymap_config.color_rating_distance(spot_infos['drivingTime'])

                    popupText = '🌊 Spot : ' + nomSpot + '<br>🏁 Distance : ' + str(round(spot_infos['drivingDist'], 1)) + ' km<br>⏳ Temps de trajet : ' + str(round(spot_infos['drivingTime'], 1)) + ' h<br>💸 Prix (aller) : ' + str(round(spot_infos['prix'], 2)) + ' €<br>🏄‍♂️ Prévisions (' + selectbox_daily_forecast + ') : ' + str(spot_forecast) + " /10"
                    popupSpot = folium.Popup(popupText,
                                             max_width = '220')
                    marker = folium.Marker(location = spot_infos['gpsSpot'],
                                           popup = popupSpot,
                                           icon = folium.Icon(color = colorIcon, icon = ''))
                    marker.add_to(m)
                except Exception as e:
                    print("Spot suivant non affiché : " + str(nomSpot))
                    pass

            if len(dfDataDisplay) > 0:
                st.sidebar.success("Recherche terminée (" + str(len(dfDataDisplay)) + " résultats) !")
            if len(dfDataDisplay) == 0:
                m = folium.Map(location = base_position,
                               zoom_start = 6)
                st.sidebar.error("Aucun résultat trouvé")
    else:
        m = folium.Map(location = base_position,
                       zoom_start = 6)
        st.warning('Aucune adresse sélectionnée')

    folium_static(m)

    st.markdown("- - -")

    st.markdown(":copyright: 2021-2022 Paul Bâcle")

main()
