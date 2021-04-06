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
#documents d'upload : https://github.com/MaartenGr/streamlit_guide
#source : https://towardsdatascience.com/quickly-build-and-deploy-an-application-with-streamlit-988ca08c7e83

st.title('Surfmap')
base_position = [48.8434864, 2.3859893]

#Sidebar & data
label_address = "Renseignez votre ville"
address = st.sidebar.text_input(label_address, value = '',
                                max_chars = None, key = None, type = 'default', help = None)
dfSpots = surfmap_config.load_data()

def main():
    st.markdown("Bienvenue dans l'application :ocean: Surfmap !")
    st.markdown("Cette application a pour but de vous aider à identifier le meilleur spot de surf accessible depuis votre ville ! Bon ride :surfer:")

    explication_expander = st.beta_expander("Guide d'utilisation")
    with explication_expander:
        st.write("Vous pourrez trouver ci-dessous une carte affichant les principaux spots de surf accessibles depuis votre ville. Pour cela, il suffit d'indiquer dans la barre de gauche votre position et appuyer sur 'Soumettre l'adresse'.")
        st.write("La carte qui s'affiche ci-dessous indique votre position (en bleu) ainsi que les différents spots en proposant les meilleurs spots (en vert, modifiable ci-dessous dans 'code couleur') et en affichant les informations du spot lorsque vous cliquez dessus.")
        st.write("Vous pouvez affiner les spots proposés en sélectionnant les options avancées et en filtrant sur vos prérequis. Ces choix peuvent porter sur (i) le prix maximum par aller, (ii) le temps de parcours acceptable, (iii) le pays de recherche et (iv) les conditions de spot recherchées !")
        st.warning("Les choix par conditions de surf ne sont pas encore disponibles et le seront dans la prochaine release")

    couleur_radio_expander = st.beta_expander("Légende de la carte")
    with couleur_radio_expander:
        #st.markdown("_Légende :_")
        st.markdown(":triangular_flag_on_post: représente un spot de surf")
        st.markdown("La couleur donne la qualité du spot à partir de vos critères : :green_book: parfait, :orange_book: moyen, :closed_book: déconseillé")
        #st.markdown("_Choisir le code couleur (optionnel) :_")
        label_radio_choix_couleur = "Vous pouvez choisir ci-dessous un code couleur pour faciliter l'identification des spots en fonction de vos critères (distance par défaut)"
        list_radio_choix_couleur = ["🕔 Distance", "💸 Prix"]
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
    sidebar_profil = st.sidebar.beta_expander(label_sidebar_profil)
    with sidebar_profil:
        #st.markdown("Quel type de surfer es-tu ?")
        st.warning("Work in progress")
        label_transport = "Moyen(s) de transport(s) favori(s)"
        list_transport = ["🚗 Voiture", "🚝 Train", "🚲 Vélo", "⛵ Bateau"]
        multiselect_transport = st.multiselect(label_transport, list_transport,
                                          default = list_transport[0])

    label_sidebar_options = "Options avancées"
    sidebar_options = st.sidebar.beta_expander(label_sidebar_options)
    with sidebar_options:
        st.markdown("Choix des options pour l'affichage des spots")
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

        label_choix_pays = "Choix des pays"
        list_pays = ["🇫🇷 France", "🇪🇸 Espagne", "🇮🇹 Italie"]
        multiselect_pays = st.multiselect(label_choix_pays, list_pays,
                                          default = list_pays[0],
                                          key = session.run_id)

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

            multiselect_pays = [x.split()[-1] for x in multiselect_pays] #permet d'enlever les émoji pour la recherche
            dfData = dfData[dfData['paysSpot'].isin(multiselect_pays)]

            for nomSpot in dfData['nomSpot'].tolist():
                spot_infos = dict_data_from_address[nomSpot]
                #if option_prix > 0 or option_distance_h > 0:
                #    colorIcon = surfmap_config.color_rating_criteria(is_option_prix_ok, is_option_distance_h_ok)
                #else:
                if checkbox_choix_couleur == list_radio_choix_couleur[-1]: #corresponds à "prix" avec l'icône associée
                    colorIcon = surfmap_config.color_rating_prix(spot_infos['prix'])
                else:
                    colorIcon = surfmap_config.color_rating_distance(spot_infos['drivingTime'])
                popupSpot = folium.Popup('Spot : ' + nomSpot + ', distance : ' + str(round(spot_infos['drivingDist'], 1)) + ' km, temps de trajet : '
                                         + str(round(spot_infos['drivingTime'], 1)) + ' h, prix (aller): '
                                         + str(round(spot_infos['prix'], 2)) + ' €',
                                         max_width = '220')
                marker = folium.Marker(location = spot_infos['gps'],
                                       popup = popupSpot,
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
        st.warning('Aucune adresse sélectionnée')

    folium_static(m)

    st.markdown("- - -")

    st.markdown(":copyright: 2021 Paul Bâcle")

main()

#Tracer
