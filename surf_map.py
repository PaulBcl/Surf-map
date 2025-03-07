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
logging.basicConfig(level=logging.INFO)
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

st.title('Surfmap')
base_position = [48.8434864, 2.3859893]

# Initialize session state
session = get_session()

def setup_sidebar():
    """Set up the sidebar with all controls."""
    # Welcome message and instructions
    st.markdown("Bienvenue dans l'application :ocean: Surfmap !")
    st.markdown("Cette application a pour but de vous aider à identifier le meilleur spot de surf accessible depuis votre ville ! Bon ride :surfer:")
    st.success("New release🌴! Les conditions de surf sont désormais disponibles pour optimiser votre recherche !")

    # Guide d'utilisation
    explication_expander = st.expander("Guide d'utilisation")
    with explication_expander:
        st.write("Vous pourrez trouver ci-dessous une carte affichant les principaux spots de surf accessibles depuis votre ville. Pour cela, il suffit d'indiquer dans la barre de gauche votre position et appuyer sur 'Soumettre l'adresse'.")
        st.write("La carte qui s'affiche ci-dessous indique votre position (🏠 en bleu) ainsi que les différents spots en proposant les meilleurs spots (en vert 📗, modifiable ci-dessous dans 'code couleur') et en affichant les informations du spot lorsque vous cliquez dessus.")
        st.write("Vous pouvez affiner les spots proposés en sélectionnant les options avancées et en filtrant sur vos prérequis. Ces choix peuvent porter sur (i) le prix (💸) maximum par aller, (ii) le temps de parcours (⏳) acceptable, (iii) le pays de recherche (🇫🇷) et (iv) les conditions prévues (🏄) des spots recherchés !")

    # Legend
    couleur_radio_expander = st.expander("Légende de la carte")
    with couleur_radio_expander:
        st.markdown(":triangular_flag_on_post: représente un spot de surf")
        st.markdown("La couleur donne la qualité du spot à partir de vos critères : :green_book: parfait, :orange_book: moyen, :closed_book: déconseillé")
        label_radio_choix_couleur = "Vous pouvez choisir ci-dessous un code couleur pour faciliter l'identification des spots en fonction de vos critères (prévisions du spot par défaut)"
        list_radio_choix_couleur = ["🏄‍♂️ Prévisions", "🏁 Distance", "💸 Prix"]
        checkbox_choix_couleur = st.selectbox(label_radio_choix_couleur, list_radio_choix_couleur)

    # Address input
    label_address = "Renseignez votre ville"
    address = st.sidebar.text_input(label_address, value='', max_chars=None, key=None, type='default', help=None)
    
    # Profile section
    with st.sidebar.expander("Profil"):
        st.warning("Work in progress")
        label_transport = "Moyen(s) de transport(s) favori(s)"
        list_transport = ["🚗 Voiture", "🚝 Train", "🚲 Vélo", "⛵ Bateau"]
        multiselect_transport = st.multiselect(label_transport, list_transport, default=list_transport[0])
    
    # Advanced options section
    with st.sidebar.expander("Options avancées"):
        # Reset button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            raz_button = st.button("Remise à zéro", key=None, help="Remettre les options à zéro")
        
        if raz_button:
            session.run_id += 1
        
        # Forecast day selection
        label_daily_forecast = "Jour souhaité pour l'affichage des prévisions de surf"
        selectbox_daily_forecast = st.selectbox(label_daily_forecast, dayList)
        
        # Sliders
        option_forecast = st.slider("Conditions minimum souhaitées (/10)", min_value=0, max_value=10,
                                  key=session.run_id, help="En définissant les prévisions à 0, tous les résultats s'affichent")
        option_prix = st.slider("Prix maximum souhaité (€, pour un aller)", min_value=0, max_value=200,
                              key=session.run_id, help="En définissant le prix à 0€, tous les résultats s'affichent")
        option_distance_h = st.slider("Temps de conduite souhaité (heures)", min_value=0, max_value=15,
                                    key=session.run_id, help="En définissant le temps maximal de conduite à 0h, tous les résultats s'affichent")
        
        # Country selection
        label_choix_pays = "Choix des pays pour les spots à afficher"
        list_pays = ["🇫🇷 France", "🇪🇸 Espagne", "🇮🇹 Italie"]
        multiselect_pays = st.multiselect(label_choix_pays, list_pays, default=list_pays[0], key=session.run_id)
    
    # Submit button
    st.sidebar.write("\n")
    col1, col2, col3 = st.sidebar.columns([1, 3.5, 1])
    with col2:
        validation_button = st.button("Soumettre l'adresse", key=None, help=None)
    
    return address, validation_button, option_forecast, option_prix, option_distance_h, selectbox_daily_forecast, multiselect_pays, checkbox_choix_couleur

def apply_filters(dfDataDisplay, option_prix, option_distance_h, option_forecast, multiselect_pays):
    """Apply all filters to the DataFrame."""
    if dfDataDisplay.empty:
        return dfDataDisplay
    
    # Price filter
    if option_prix > 0 and 'prix' in dfDataDisplay.columns:
        dfDataDisplay = dfDataDisplay[dfDataDisplay['prix'].astype(float) <= option_prix].copy()
    
    # Distance filter
    if option_distance_h > 0 and 'drivingTime' in dfDataDisplay.columns:
        dfDataDisplay = dfDataDisplay[dfDataDisplay['drivingTime'].astype(float) <= option_distance_h].copy()
    
    # Forecast filter
    if option_forecast > 0 and 'forecast' in dfDataDisplay.columns:
        dfDataDisplay = dfDataDisplay[dfDataDisplay['forecast'].astype(float) >= option_forecast].copy()
    
    # Country filter
    if 'paysSpot' in dfDataDisplay.columns:
        multiselect_pays = [x.split()[-1] for x in multiselect_pays]
        dfDataDisplay = dfDataDisplay[dfDataDisplay['paysSpot'].isin(multiselect_pays)].copy()
    
    return dfDataDisplay

def main():
    # Load initial data
    dfSpots, dayList = load_initial_data()
    
    # Set up sidebar and get user inputs
    address, validation_button, option_forecast, option_prix, option_distance_h, selectbox_daily_forecast, multiselect_pays, checkbox_choix_couleur = setup_sidebar()
    
    # Initialize display variables
    dfDataDisplay = pd.DataFrame()
    failed_spots = []
    
    # Process data if address is provided
    if address:
        if validation_button or option_prix >= 0 or option_distance_h >= 0 or option_forecast >= 0:
            try:
                # Load and process data
                dfData = surfmap_config.load_data(dfSpots, api_config.gmaps_api_key)
                if 'villeOrigine' in dfData.columns and address in dfData['villeOrigine'].tolist():
                    dfDataDisplay = dfData[dfData['villeOrigine'] == address].copy()
                else:
                    dfDataDisplay = process_spot_data(dfData, address, api_config.gmaps_api_key)
                
                if not dfDataDisplay.empty:
                    # Create map and add markers
                    m, marker_cluster = create_map_with_markers(dfDataDisplay, address, base_position)
                    
                    # Load forecast data
                    forecast_data = forecast_config.load_forecast_data(dfDataDisplay['nomSurfForecast'].tolist(), dayList)
                    
                    # Apply filters
                    dfDataDisplay = apply_filters(dfDataDisplay, option_prix, option_distance_h, option_forecast, multiselect_pays)
                    
                    # Add markers for each spot
                    for nomSpot in dfDataDisplay['nomSpot'].tolist():
                        add_spot_marker(dfDataDisplay, nomSpot, marker_cluster, forecast_data, selectbox_daily_forecast, checkbox_choix_couleur)
                    
                    st.sidebar.success(f"Recherche terminée ({len(dfDataDisplay)} résultats) !")
                else:
                    st.sidebar.error("Aucun résultat trouvé")
                    
            except Exception as e:
                st.error(f"Erreur lors du traitement des données: {str(e)}")
    else:
        st.warning('Aucune adresse sélectionnée')
    
    # Display the map
    st_folium(m, returned_objects=[], width=800, height=600)
    
    # Display failed spots
    if failed_spots:
        with st.expander("⚠️ Spots non affichés sur la carte", expanded=False):
            st.write("Les spots suivants n'ont pas pu être affichés sur la carte :")
            for spot in failed_spots:
                st.write(f"- {spot['name']} : {spot['reason']}")
    
    st.markdown("- - -")
    st.markdown(":copyright: 2021-2025 Paul Bâcle")

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_initial_data():
    """Load and cache initial data that doesn't change frequently."""
    try:
        url_database = "surfmap_config/surfspots.xlsx"
        dfSpots = surfmap_config.load_spots(url_database)
        dayList = forecast_config.get_dayList_forecast()
        return dfSpots, dayList
    except Exception as e:
        st.error(f"Error loading spots database: {str(e)}")
        return pd.DataFrame(), []

@st.cache_data(ttl=3600)
def process_spot_data(dfData, address, api_key):
    """Process spot data for a given address."""
    try:
        dfSearchVille = research_config.add_new_spot_to_dfData(address, dfData, api_key)
        if dfSearchVille is not None and not dfSearchVille.empty:
            common_columns = list(set(dfData.columns) & set(dfSearchVille.columns))
            dfData = dfData[common_columns].copy()
            dfSearchVille = dfSearchVille[common_columns].copy()
            
            numeric_columns = ['drivingDist', 'drivingTime', 'tollCost', 'gazPrice', 'prix', 'forecast']
            for col in numeric_columns:
                if col in common_columns:
                    dfData[col] = pd.to_numeric(dfData[col], errors='coerce').fillna(0.0)
                    dfSearchVille[col] = pd.to_numeric(dfSearchVille[col], errors='coerce').fillna(0.0)
            
            if not (dfData.empty and dfSearchVille.empty):
                dfData = pd.concat([dfData, dfSearchVille], ignore_index=True)
                return dfData[dfData['villeOrigine'] == address].copy()
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error processing spot data: {str(e)}")
        return pd.DataFrame()

def add_spot_marker(dfDataDisplay, nomSpot, marker_cluster, forecast_data, selectbox_daily_forecast, checkbox_choix_couleur):
    """Add a marker for a specific spot to the map."""
    try:
        spot_infos_df = dfDataDisplay[dfDataDisplay['nomSpot'] == nomSpot].copy()
        if spot_infos_df.empty:
            return
            
        spot_infos = spot_infos_df.to_dict('records')[0]
        spot_coords = spot_infos.get('gpsSpot')
        
        # Skip if coordinates are invalid
        if not spot_coords or not isinstance(spot_coords, (list, tuple)) or len(spot_coords) != 2:
            failed_spots.append({
                'name': nomSpot,
                'reason': 'Invalid coordinates'
            })
            return
            
        lat, lon = spot_coords
        if lat is None or lon is None:
            failed_spots.append({
                'name': nomSpot,
                'reason': 'Invalid coordinates'
            })
            return
            
        # Get route information
        driving_dist = spot_infos.get('drivingDist', 0.0)
        driving_time = spot_infos.get('drivingTime', 0.0)
        prix = spot_infos.get('prix', 0.0)
        
        # Convert route values to float, handling None/NaN
        try:
            driving_dist = float(driving_dist) if driving_dist is not None and not pd.isna(driving_dist) else 0.0
            driving_time = float(driving_time) if driving_time is not None and not pd.isna(driving_time) else 0.0
            prix = float(prix) if prix is not None and not pd.isna(prix) else 0.0
        except (ValueError, TypeError):
            driving_dist = 0.0
            driving_time = 0.0
            prix = 0.0
        
        # Get forecast value
        try:
            spot_forecast = float(spot_infos.get('forecast', 0))
        except (ValueError, TypeError):
            spot_forecast = 0.0
        
        # Determine marker color based on selected criteria
        if checkbox_choix_couleur == "💸 Prix":
            colorIcon = displaymap_config.color_rating_prix(prix)
        elif checkbox_choix_couleur == "🏄‍♂️ Prévisions":
            colorIcon = displaymap_config.color_rating_forecast(spot_forecast)
        else:  # Distance
            colorIcon = displaymap_config.color_rating_distance(driving_time)
        
        # Get detailed forecast data
        spot_forecast_details = forecast_data.get(nomSpot, {})
        current_forecast = None
        if spot_forecast_details and isinstance(spot_forecast_details, dict):
            for forecast in spot_forecast_details.get('forecasts', []):
                if forecast.timestamp.strftime('%A %d') in selectbox_daily_forecast:
                    current_forecast = forecast
                    break
        
        # Create popup text with detailed forecast information
        popupText = (
            f'🌊 Spot : {nomSpot}<br>'
            f'🏁 Distance : {driving_dist:.1f} km<br>'
            f'⏳ Temps de trajet : {driving_time:.1f} h<br>'
            f'💸 Prix (aller) : {prix:.2f} €<br>'
        )
        
        if current_forecast:
            popupText += (
                f'🏄‍♂️ Prévisions ({selectbox_daily_forecast}):<br>'
                f'&nbsp;&nbsp;• Note : {current_forecast.rating}/10<br>'
                f'&nbsp;&nbsp;• Hauteur : {current_forecast.wave_height}<br>'
                f'&nbsp;&nbsp;• Période : {current_forecast.wave_period}<br>'
                f'&nbsp;&nbsp;• Énergie : {current_forecast.wave_energy}<br>'
                f'&nbsp;&nbsp;• Vent : {current_forecast.wind_speed}'
            )
        else:
            popupText += f'🏄‍♂️ Prévisions ({selectbox_daily_forecast}) : {spot_forecast:.1f}/10'
            
        try:
            popupSpot = folium.Popup(popupText, max_width='220')
        except Exception:
            popupSpot = folium.Popup(f'🌊 Spot : {nomSpot}', max_width='220')
        
        # Add marker to map
        try:
            marker = folium.Marker(
                location=[float(lat), float(lon)],
                popup=popupSpot,
                icon=folium.Icon(color=colorIcon, icon='')
            )
            marker.add_to(marker_cluster)
        except Exception as e:
            failed_spots.append({
                'name': nomSpot,
                'reason': f'Error adding marker: {str(e)}'
            })
            
    except Exception as e:
        failed_spots.append({
            'name': nomSpot,
            'reason': f'Error processing spot: {str(e)}'
        })

def create_map_with_markers(dfDataDisplay, address, base_position):
    """Create and configure the map with markers."""
    # Initialize map with default position
    m = folium.Map(location=base_position, zoom_start=6)
    
    # Add map components
    marker_cluster = MarkerCluster().add_to(m)
    minimap = MiniMap(toggle_display=True)
    draw = Draw()
    minimap.add_to(m)
    draw.add_to(m)
    
    # Update map location if we have valid coordinates
    if 'gpsVilleOrigine' in dfDataDisplay.columns and dfDataDisplay['gpsVilleOrigine'].iloc[0] is not None:
        try:
            coords = dfDataDisplay['gpsVilleOrigine'].iloc[0]
            if isinstance(coords, (list, tuple)) and len(coords) == 2:
                lat, lon = coords
                if lat is not None and lon is not None:
                    m = folium.Map(location=[float(lat), float(lon)], zoom_start=5)
                    # Add home marker
                    popupHome = folium.Popup("💑 Maison", max_width='150')
                    folium.Marker(
                        location=[float(lat), float(lon)],
                        popup=popupHome,
                        icon=folium.Icon(color='blue', icon='home')
                    ).add_to(m)
                    
                    # Re-add map components after map reinitialization
                    marker_cluster = MarkerCluster().add_to(m)
                    minimap = MiniMap(toggle_display=True)
                    draw = Draw()
                    minimap.add_to(m)
                    draw.add_to(m)
        except Exception as e:
            st.error(f"Error updating map location: {str(e)}")
    
    return m, marker_cluster

# Initialize failed_spots list at module level
failed_spots = []

main()
