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
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

# Initialize debug information storage
if 'debug_info' not in st.session_state:
    st.session_state.debug_info = []

def add_debug_info(message, level="INFO"):
    """Add debug information to the session state"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_info.append(f"[{timestamp}] {level}: {message}")

st.title('Surfmap')
base_position = [48.8434864, 2.3859893]

# Add debug expander at the start
with st.expander("🔍 Debug Information", expanded=True):
    st.write("This section shows detailed information about the application's operation and any potential issues.")
    if st.button("Clear Debug Log"):
        st.session_state.debug_info = []
    for message in st.session_state.debug_info:
        st.text(message)

# Initialize session state
session = get_session()

#Sidebar & data
label_address = "Renseignez votre ville"
address = st.sidebar.text_input(label_address, value = '',
                                max_chars = None, key = None, type = 'default', help = None)

#On peuple la base de données
try:
    url_database = "surfmap_config/surfspots.xlsx"
    dfSpots = surfmap_config.load_spots(url_database)
    add_debug_info(f"Successfully loaded spots database with {len(dfSpots)} entries")
    dayList = forecast_config.get_dayList_forecast()
    add_debug_info(f"Successfully loaded forecast days: {dayList}")
except Exception as e:
    add_debug_info(f"Error loading spots database: {str(e)}", "ERROR")
    add_debug_info(traceback.format_exc(), "ERROR")
    st.error(f"Error loading spots database: {str(e)}")
    dfSpots = pd.DataFrame()
    dayList = []

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
    # Initialize failed_spots list
    failed_spots = []
    
    try:
        dfData = surfmap_config.load_data(dfSpots, api_config.gmaps_api_key)
        add_debug_info(f"Successfully loaded data with {len(dfData)} entries")
        add_debug_info(f"DataFrame columns: {dfData.columns.tolist()}")
    except Exception as e:
        add_debug_info(f"Error loading data: {str(e)}", "ERROR")
        add_debug_info(traceback.format_exc(), "ERROR")
        st.error(f"Error loading data: {str(e)}")
        dfData = pd.DataFrame()

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
                        # Ensure both DataFrames have the same columns and handle empty/NA values
                        common_columns = list(set(dfData.columns) & set(dfSearchVille.columns))
                        dfData = dfData[common_columns].copy()
                        dfSearchVille = dfSearchVille[common_columns].copy()
                        
                        # Fill NA values with appropriate defaults
                        numeric_columns = ['drivingDist', 'drivingTime', 'tollCost', 'gazPrice', 'prix', 'forecast']
                        for col in numeric_columns:
                            if col in common_columns:
                                dfData[col] = pd.to_numeric(dfData[col], errors='coerce').fillna(0.0)
                                dfSearchVille[col] = pd.to_numeric(dfSearchVille[col], errors='coerce').fillna(0.0)
                        
                        # Handle empty DataFrames before concatenation
                        if dfData.empty and dfSearchVille.empty:
                            dfDataDisplay = pd.DataFrame()
                        else:
                            # Concatenate the DataFrames
                            dfData = pd.concat([dfData, dfSearchVille], ignore_index=True)
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
                        if isinstance(coords, (list, tuple)) and len(coords) == 2:
                            lat, lon = coords
                            if lat is not None and lon is not None:
                                gpsHome = [float(lat), float(lon)]
                            else:
                                raise ValueError("Invalid coordinates")
                        else:
                            raise ValueError("Invalid coordinate format")
                    else:
                        raise ValueError("No valid coordinates found")
                except (ValueError, TypeError, IndexError) as e:
                    st.error(f"Impossible de trouver les coordonnées GPS pour l'adresse '{address}'. Veuillez vérifier l'adresse et réessayer.")
                    gpsHome = base_position  # Use default coordinates

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
                    except (ValueError, TypeError, IndexError) as e:
                        pass  # Silently handle any errors when adding home marker
                
                minimap.add_to(m)
                draw.add_to(m)

                #Ajout des données de forecast
                try:
                    if not dfDataDisplay.empty and 'nomSurfForecast' in dfDataDisplay.columns and not dfDataDisplay['nomSurfForecast'].empty:
                        forecast_data = forecast_config.load_forecast_data(dfDataDisplay['nomSurfForecast'].tolist(), dayList)
                        dfDataDisplay.loc[:, 'forecast'] = [forecast_data.get(spot, {}).get(selectbox_daily_forecast, 0) for spot in dfDataDisplay['nomSurfForecast']]
                    else:
                        dfDataDisplay.loc[:, 'forecast'] = [0] * len(dfDataDisplay) if not dfDataDisplay.empty else []
                except Exception as e:
                    st.error("Erreur lors du chargement des prévisions de surf")
                    dfDataDisplay.loc[:, 'forecast'] = [0] * len(dfDataDisplay) if not dfDataDisplay.empty else []

                if option_prix > 0 and not dfDataDisplay.empty:
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

                if option_distance_h > 0 and not dfDataDisplay.empty:
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

                if option_forecast > 0 and not dfDataDisplay.empty:
                    try:
                        if 'forecast' in dfDataDisplay.columns:
                            dfDataDisplay = dfDataDisplay[dfDataDisplay['forecast'].astype(float) >= option_forecast].copy()
                        else:
                            st.warning("Colonne 'forecast' non trouvée")
                    except (ValueError, TypeError):
                        st.warning("Impossible de filtrer par prévisions")

                if not dfDataDisplay.empty and 'paysSpot' in dfDataDisplay.columns:
                    multiselect_pays = [x.split()[-1] for x in multiselect_pays] #permet d'enlever les émoji pour la recherche
                    dfDataDisplay = dfDataDisplay[dfDataDisplay['paysSpot'].isin(multiselect_pays)].copy()

                # Only process spots if we have valid data
                if not dfDataDisplay.empty and 'nomSpot' in dfDataDisplay.columns:
                    add_debug_info(f"Processing {len(dfDataDisplay)} spots")
                    for nomSpot in dfDataDisplay['nomSpot'].tolist():
                        spot_infos_df = dfDataDisplay[dfDataDisplay['nomSpot'] == nomSpot].copy()
                        if not spot_infos_df.empty:
                            spot_infos = spot_infos_df.to_dict('records')[0]
                            spot_coords = spot_infos.get('gpsSpot')
                            
                            # Log spot information for debugging
                            add_debug_info(f"Processing spot: {nomSpot}")
                            add_debug_info(f"Spot coordinates: {spot_coords}")
                            add_debug_info(f"Spot info: {spot_infos}")
                            
                            # Skip if coordinates are invalid
                            if not spot_coords or not isinstance(spot_coords, (list, tuple)) or len(spot_coords) != 2:
                                add_debug_info(f"Invalid coordinates for spot {nomSpot}: {spot_coords}", "WARNING")
                                failed_spots.append({
                                    'name': nomSpot,
                                    'reason': 'Invalid coordinates'
                                })
                                continue
                            
                            try:
                                lat, lon = spot_coords
                                if lat is None or lon is None:
                                    add_debug_info(f"Missing coordinates for spot {nomSpot}", "WARNING")
                                    failed_spots.append({
                                        'name': nomSpot,
                                        'reason': 'Invalid coordinates'
                                    })
                                    continue
                                    
                                # Get route information
                                driving_dist = spot_infos.get('drivingDist')
                                driving_time = spot_infos.get('drivingTime')
                                prix = spot_infos.get('prix')
                                
                                add_debug_info(f"Route info for {nomSpot}: dist={driving_dist}, time={driving_time}, prix={prix}")
                                
                                # Convert route values to float, handling None/NaN
                                try:
                                    driving_dist = float(driving_dist) if driving_dist is not None and not pd.isna(driving_dist) else 0.0
                                    driving_time = float(driving_time) if driving_time is not None and not pd.isna(driving_time) else 0.0
                                    prix = float(prix) if prix is not None and not pd.isna(prix) else 0.0
                                    add_debug_info(f"Converted route info for {nomSpot}: dist={driving_dist}, time={driving_time}, prix={prix}")
                                except (ValueError, TypeError) as e:
                                    add_debug_info(f"Error converting route values for {nomSpot}: {str(e)}", "WARNING")
                                    driving_dist = 0.0
                                    driving_time = 0.0
                                    prix = 0.0
                                
                                # Get forecast value
                                try:
                                    spot_forecast = float(spot_infos.get('forecast', 0))
                                    add_debug_info(f"Forecast for {nomSpot}: {spot_forecast}")
                                except (ValueError, TypeError, IndexError) as e:
                                    add_debug_info(f"Error getting forecast for {nomSpot}: {str(e)}", "WARNING")
                                    spot_forecast = 0.0
                                
                                # Determine marker color based on selected criteria
                                if checkbox_choix_couleur == list_radio_choix_couleur[-1]:  # Price
                                    colorIcon = displaymap_config.color_rating_prix(prix)
                                elif checkbox_choix_couleur == list_radio_choix_couleur[0]:  # Forecast
                                    colorIcon = displaymap_config.color_rating_forecast(spot_forecast)
                                else:  # Distance
                                    colorIcon = displaymap_config.color_rating_distance(driving_time)
                                
                                add_debug_info(f"Marker color for {nomSpot}: {colorIcon}")
                                
                                # Create popup text with explicit formatting
                                popupText = (
                                    f'🌊 Spot : {nomSpot}<br>'
                                    f'🏁 Distance : {driving_dist:.1f} km<br>'
                                    f'⏳ Temps de trajet : {driving_time:.1f} h<br>'
                                    f'💸 Prix (aller) : {prix:.2f} €<br>'
                                    f'🏄‍♂️ Prévisions ({selectbox_daily_forecast}) : {spot_forecast:.1f} /10'
                                )
                                add_debug_info(f"Popup text for {nomSpot}: {popupText}")
                                
                                popupSpot = folium.Popup(popupText, max_width='220')
                                
                                # Add marker to map with explicit float conversion
                                marker = folium.Marker(
                                    location=[float(lat), float(lon)],
                                    popup=popupSpot,
                                    icon=folium.Icon(color=colorIcon, icon='')
                                )
                                marker.add_to(marker_cluster)
                                add_debug_info(f"Successfully added marker for {nomSpot}")
                                
                            except Exception as e:
                                add_debug_info(f"Error processing spot {nomSpot}: {str(e)}", "ERROR")
                                add_debug_info(traceback.format_exc(), "ERROR")
                                failed_spots.append({
                                    'name': nomSpot,
                                    'reason': f'Error processing spot: {str(e)}'
                                })
                                continue

                if len(dfDataDisplay) > 0:
                    st.sidebar.success("Recherche terminée (" + str(len(dfDataDisplay)) + " résultats) !")
                if len(dfDataDisplay) == 0:
                    m = folium.Map(location=base_position, zoom_start=6)
                    st.sidebar.error("Aucun résultat trouvé")
    else:
        m = folium.Map(location = base_position,
                       zoom_start = 6)
        st.warning('Aucune adresse sélectionnée')

    # Display the map with all its components
    st_folium(m, returned_objects=[], width=800, height=600)  # Added explicit dimensions

    # Add expander for failed spots information
    if failed_spots:
        with st.expander("⚠️ Spots non affichés sur la carte", expanded=False):
            st.write("Les spots suivants n'ont pas pu être affichés sur la carte :")
            for spot in failed_spots:
                st.write(f"- {spot['name']} : {spot['reason']}")

    st.markdown("- - -")

    st.markdown(":copyright: 2021-2025 Paul Bâcle")

main()
