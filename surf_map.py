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
from SessionState import get_session
from streamlit_folium import folium_static, st_folium #https://github.com/randyzwitch/streamlit-folium
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

# Initialize session state
session = get_session()

#Sidebar & data
label_address = "Renseignez votre ville"
address = st.sidebar.text_input(label_address, value = '',
                                max_chars = None, key = None, type = 'default', help = None)

#On peuple la base de données
url_database = "surfmap_config/surfspots.xlsx"
dfSpots = surfmap_config.load_spots(url_database)
dayList = forecast_config.get_dayList_forecast()

# Initialize session state variables if they don't exist
if not hasattr(session, 'run_id'):
    session.run_id = str(time.time())
if not hasattr(session, 'address'):
    session.address = None
if not hasattr(session, 'dfData'):
    session.dfData = None
if not hasattr(session, 'map'):
    session.map = None

def main():
    # Initialize dfDataDisplay as an empty DataFrame
    dfDataDisplay = pd.DataFrame()
    
    dfData = surfmap_config.load_data(dfSpots, api_config.gmaps_api_key)

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
            #On commence par regarder si la ville recherchée a déjà été requêtée
            if 'villeOrigine' in dfData.columns and address in dfData['villeOrigine'].tolist():
                dfDataDisplay = dfData[dfData['villeOrigine'] == address].copy()  # Create a copy to avoid SettingWithCopyWarning
            else: #cas où la ville n'a jamais été requêtée
                try:
                    dfSearchVille = research_config.add_new_spot_to_dfData(address, dfData, api_config.gmaps_api_key)
                    if dfSearchVille is not None and not dfSearchVille.empty:
                        dfData = pd.concat([dfData, dfSearchVille]) #appel à la fonction de merging de research_config
                        dfDataDisplay = dfData[dfData['villeOrigine'] == address].copy()  # Create a copy
                    else:
                        st.error(f"Impossible de trouver des spots pour l'adresse '{address}'")
                        dfDataDisplay = pd.DataFrame()
                except Exception as e:
                    st.error(f"Erreur lors de la recherche des spots: {str(e)}")
                    dfDataDisplay = pd.DataFrame()

            if not dfDataDisplay.empty:
                # Ensure all required columns exist with default values
                required_columns = {
                    'gpsVilleOrigine': None,
                    'paysSpot': None,
                    'nomSurfForecast': None,
                    'prix': 0.0,
                    'drivingTime': 0.0,
                    'drivingDist': 0.0,
                    'nomSpot': None,
                    'gpsSpot': None,
                    'forecast': 0.0
                }
                
                for col, default_value in required_columns.items():
                    if col not in dfDataDisplay.columns:
                        dfDataDisplay[col] = default_value

                # Check if we have valid GPS coordinates
                try:
                    if 'gpsVilleOrigine' in dfDataDisplay.columns and dfDataDisplay['gpsVilleOrigine'].iloc[0] is not None:
                        coords = dfDataDisplay['gpsVilleOrigine'].iloc[0]
                        st.write(f"Raw coordinates from DataFrame: {coords}")  # Debug info
                        if isinstance(coords, (list, tuple)) and len(coords) == 2:
                            lat, lon = coords
                            if lat is not None and lon is not None:
                                gpsHome = [float(lat), float(lon)]
                                st.write(f"Using GPS coordinates for {address}: {gpsHome}")  # Debug info
                            else:
                                raise ValueError("Invalid coordinates")
                        else:
                            raise ValueError("Invalid coordinate format")
                    else:
                        raise ValueError("No valid coordinates found")
                except (ValueError, TypeError, IndexError) as e:
                    st.error(f"Impossible de trouver les coordonnées GPS pour l'adresse '{address}'. Veuillez vérifier l'adresse et réessayer.")
                    gpsHome = base_position  # Use default coordinates
                    st.write(f"Using default coordinates: {gpsHome}")  # Debug info

                #Display maps
                m = folium.Map(location = gpsHome,
                               zoom_start = 5)
                #Petits ajouts
                marker_cluster = MarkerCluster().add_to(m)
                minimap = MiniMap(toggle_display = True)
                draw = Draw()
                
                # Only add home marker if we have valid data
                if not dfDataDisplay.empty and 'gpsVilleOrigine' in dfDataDisplay.columns and dfDataDisplay['gpsVilleOrigine'].iloc[0] is not None:
                    try:
                        coords = dfDataDisplay['gpsVilleOrigine'].iloc[0]
                        if isinstance(coords, (list, tuple)) and len(coords) == 2:
                            lat, lon = coords
                            if lat is not None and lon is not None:
                                popupHome = folium.Popup("💑 Maison",
                                                         max_width = '150')
                                folium.Marker(location = [float(lat), float(lon)],
                                              popup = popupHome,
                                              icon = folium.Icon(color = 'blue', icon = 'home')).add_to(m)
                                st.write(f"Added home marker at {lat}, {lon}")  # Debug info
                    except (ValueError, TypeError, IndexError) as e:
                        st.write(f"Error adding home marker: {str(e)}")  # Debug info
                
                minimap.add_to(m)
                draw.add_to(m)

                #Ajout des données de forecast
                try:
                    if 'nomSurfForecast' in dfDataDisplay.columns and not dfDataDisplay['nomSurfForecast'].empty:
                        forecast_data = forecast_config.load_forecast_data(dfDataDisplay['nomSurfForecast'].tolist(), dayList)
                        dfDataDisplay.loc[:, 'forecast'] = [forecast_data.get(spot, {}).get(selectbox_daily_forecast, 0) for spot in dfDataDisplay['nomSurfForecast']]
                    else:
                        dfDataDisplay.loc[:, 'forecast'] = [0] * len(dfDataDisplay)
                except Exception as e:
                    st.error("Erreur lors du chargement des prévisions de surf")
                    dfDataDisplay.loc[:, 'forecast'] = [0] * len(dfDataDisplay)  # Default to 0 if forecast fails

                if option_prix > 0:
                    try:
                        if 'prix' in dfDataDisplay.columns:
                            dfDataDisplay = dfDataDisplay[dfDataDisplay['prix'].astype(float) <= option_prix].copy()
                            is_option_prix_ok = True
                        else:
                            st.warning("Colonne 'prix' non trouvée")
                            is_option_prix_ok = False
                    except (ValueError, TypeError):
                        st.warning("Impossible de filtrer par prix")
                        is_option_prix_ok = False

                if option_distance_h > 0:
                    try:
                        if 'drivingTime' in dfDataDisplay.columns:
                            dfDataDisplay = dfDataDisplay[dfDataDisplay['drivingTime'].astype(float) <= option_distance_h].copy()
                            is_option_distance_h_ok = True
                        else:
                            st.warning("Colonne 'drivingTime' non trouvée")
                            is_option_distance_h_ok = False
                    except (ValueError, TypeError):
                        st.warning("Impossible de filtrer par temps de trajet")
                        is_option_distance_h_ok = False

                if option_forecast > 0:
                    try:
                        if 'forecast' in dfDataDisplay.columns:
                            dfDataDisplay = dfDataDisplay[dfDataDisplay['forecast'].astype(float) >= option_forecast].copy()
                        else:
                            st.warning("Colonne 'forecast' non trouvée")
                    except (ValueError, TypeError):
                        st.warning("Impossible de filtrer par prévisions")

                if 'paysSpot' in dfDataDisplay.columns:
                    multiselect_pays = [x.split()[-1] for x in multiselect_pays] #permet d'enlever les émoji pour la recherche
                    dfDataDisplay = dfDataDisplay[dfDataDisplay['paysSpot'].isin(multiselect_pays)].copy()

                # Only process spots if we have valid data
                if not dfDataDisplay.empty and 'nomSpot' in dfDataDisplay.columns:
                    st.write(f"Processing {len(dfDataDisplay)} spots...")  # Debug info
                    st.write(f"DataFrame columns: {dfDataDisplay.columns.tolist()}")  # Debug DataFrame structure
                    
                    for nomSpot in dfDataDisplay['nomSpot'].tolist():
                        spot_infos_df = dfDataDisplay[dfDataDisplay['nomSpot'] == nomSpot].copy()
                        if not spot_infos_df.empty:
                            spot_infos = spot_infos_df.to_dict('records')[0]
                            
                            # Debug info for spot coordinates
                            spot_coords = spot_infos.get('gpsSpot')
                            st.write(f"Spot {nomSpot} coordinates: {spot_coords}")  # Debug info
                            st.write(f"Spot {nomSpot} full info: {spot_infos}")  # Debug full spot info

                            try:
                                spot_forecast = float(dfDataDisplay[dfDataDisplay['nomSpot'] == nomSpot]['forecast'].iloc[0])
                                if checkbox_choix_couleur == list_radio_choix_couleur[-1]: #corresponds à "prix" avec l'icône associée
                                    try:
                                        if 'prix' in spot_infos:
                                            colorIcon = displaymap_config.color_rating_prix(float(spot_infos['prix']))
                                        else:
                                            colorIcon = 'gray'
                                    except (ValueError, TypeError):
                                        colorIcon = 'gray'  # Default color if price conversion fails
                                elif checkbox_choix_couleur == list_radio_choix_couleur[0]: #corresponds à "forecast" avec l'icône associée
                                    colorIcon = displaymap_config.color_rating_forecast(spot_forecast)
                                else:
                                    try:
                                        if 'drivingTime' in spot_infos:
                                            colorIcon = displaymap_config.color_rating_distance(float(spot_infos['drivingTime']))
                                        else:
                                            colorIcon = 'gray'
                                    except (ValueError, TypeError):
                                        colorIcon = 'gray'  # Default color if time conversion fails

                                try:
                                    driving_dist = float(spot_infos.get('drivingDist', 0))
                                    driving_time = float(spot_infos.get('drivingTime', 0))
                                    prix = float(spot_infos.get('prix', 0))
                                except (ValueError, TypeError):
                                    driving_dist = 0
                                    driving_time = 0
                                    prix = 0

                                popupText = f'🌊 Spot : {nomSpot}<br>🏁 Distance : {round(driving_dist, 1)} km<br>⏳ Temps de trajet : {round(driving_time, 1)} h<br>💸 Prix (aller) : {round(prix, 2)} €<br>🏄‍♂️ Prévisions ({selectbox_daily_forecast}) : {spot_forecast} /10'
                                popupSpot = folium.Popup(popupText,
                                                         max_width = '220')
                                
                                try:
                                    if isinstance(spot_coords, (list, tuple)) and len(spot_coords) == 2:
                                        lat, lon = spot_coords
                                        if lat is not None and lon is not None:
                                            marker = folium.Marker(location = [float(lat), float(lon)],
                                                                   popup = popupSpot,
                                                                   icon = folium.Icon(color = colorIcon, icon = ''))
                                            marker.add_to(marker_cluster)  # Add to marker cluster instead of map directly
                                            st.write(f"Added marker for spot {nomSpot} at coordinates {lat}, {lon}")  # Debug info
                                        else:
                                            st.write(f"Invalid coordinates for spot {nomSpot}: {spot_coords}")  # Debug info
                                    else:
                                        st.write(f"Invalid coordinate format for spot {nomSpot}: {spot_coords}")  # Debug info
                                except (ValueError, TypeError, IndexError) as e:
                                    st.write(f"Error adding marker for spot {nomSpot}: {str(e)}")  # Debug info
                                    continue

                            except Exception as e:
                                st.write(f"Error processing spot {nomSpot}: {str(e)}")  # Debug info
                                continue

                if len(dfDataDisplay) > 0:
                    st.sidebar.success("Recherche terminée (" + str(len(dfDataDisplay)) + " résultats) !")
                    st.write(f"Map should display {len(dfDataDisplay)} spots")  # Debug info
                    st.write(f"Final DataFrame structure: {dfDataDisplay.head()}")  # Debug final DataFrame
                if len(dfDataDisplay) == 0:
                    m = folium.Map(location = base_position,
                                   zoom_start = 6)
                    st.sidebar.error("Aucun résultat trouvé")
    else:
        m = folium.Map(location = base_position,
                       zoom_start = 6)
        st.warning('Aucune adresse sélectionnée')

    # Display the map with all its components
    st_folium(m, returned_objects=[], width=800, height=600)  # Added explicit dimensions

    # Add expander for failed spots information
    failed_spots = []
    if not dfDataDisplay.empty and 'nomSpot' in dfDataDisplay.columns:
        for nomSpot in dfDataDisplay['nomSpot'].tolist():
            spot_infos_df = dfDataDisplay[dfDataDisplay['nomSpot'] == nomSpot].copy()
            if not spot_infos_df.empty:
                spot_infos = spot_infos_df.to_dict('records')[0]
                spot_coords = spot_infos.get('gpsSpot')
                if not spot_coords or not isinstance(spot_coords, (list, tuple)) or len(spot_coords) != 2:
                    failed_spots.append({
                        'name': nomSpot,
                        'reason': 'Invalid coordinates'
                    })
                elif spot_infos.get('drivingDist') is None or spot_infos.get('drivingTime') is None:
                    failed_spots.append({
                        'name': nomSpot,
                        'reason': 'Could not calculate route'
                    })

    if failed_spots:
        with st.expander("⚠️ Spots non affichés sur la carte", expanded=False):
            st.write("Les spots suivants n'ont pas pu être affichés sur la carte :")
            for spot in failed_spots:
                st.write(f"- {spot['name']} : {spot['reason']}")

    st.markdown("- - -")

    st.markdown(":copyright: 2021-2025 Paul Bâcle")

main()
