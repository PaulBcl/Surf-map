#!/usr/bin/env python
# coding: utf-8

import streamlit as st
from streamlit_folium import st_folium

# Set page config - MUST BE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="🌴 SurfMap",
    page_icon="🏄‍♂️",
    layout="wide"
)

import folium
from folium import plugins
from folium.plugins import MarkerCluster, MiniMap, Draw
import pandas as pd
from datetime import datetime, timedelta
from surfmap_config import forecast_config, displaymap_config
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a session state for the reset functionality
if 'run_id' not in st.session_state:
    st.session_state.run_id = 0

def get_user_location():
    """Get user's current location using Streamlit's geolocation."""
    try:
        # Request location from user
        location = st.experimental_get_user_location()
        if location and location['coords']['latitude'] and location['coords']['longitude']:
            return [location['coords']['latitude'], location['coords']['longitude']]
        return None
    except Exception as e:
        logger.error(f"Error getting user location: {str(e)}")
        return None

def create_responsive_layout(day_list):
    """Create a responsive layout for the application."""
    # Welcome block - full width, simplified
    st.markdown("""
    <div style='text-align: center; margin-bottom: 1.5rem;'>
        <h1 style='margin-bottom: 1rem; font-size: 1.8rem;'>Bienvenue dans l'application 🌊 Surfmap !</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Create two columns for date selection and location input
    col1, col2 = st.columns(2)
    
    with col1:
        # Date selection with calendar
        st.markdown("#### 📅 Sélectionnez votre journée")
        today = datetime.now()
        selected_date = st.date_input(
            "Choisissez le jour pour vos prévisions",
            min_value=today.date(),
            max_value=today.date() + timedelta(days=6),
            value=today.date(),
            format="DD/MM/YYYY"
        )
        # Convert the selected date to the format expected by the rest of the application
        selectbox_daily_forecast = selected_date.strftime('%A %d').replace('0', ' ').lstrip()
    
    with col2:
        # Location input
        st.markdown("#### 📍 Votre position")
        address = st.text_input(
            "Entrez votre ville ou adresse",
            placeholder="ex: Biarritz, France",
            help="Si la géolocalisation ne fonctionne pas, entrez votre position manuellement"
        )
    
    # Filters in sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Filtres")
        
        # Forecast quality filter
        option_forecast = st.slider(
            "Qualité minimum des prévisions",
            min_value=0,
            max_value=10,
            value=0,
            step=1,
            help="Filtrer les spots selon la qualité des prévisions"
        )
        
        # Price filter
        option_prix = st.slider(
            "Budget maximum (€)",
            min_value=0,
            max_value=100,
            value=100,
            step=5,
            help="Filtrer les spots selon le coût du trajet"
        )
        
        # Distance/time filter
        option_distance_h = st.slider(
            "Temps de trajet maximum (heures)",
            min_value=0,
            max_value=12,
            value=12,
            step=1,
            help="Filtrer les spots selon le temps de trajet"
        )
        
        # Country selection
        multiselect_pays = st.multiselect(
            "Pays",
            ["🇫🇷 France", "🇪🇸 Espagne", "🇵🇹 Portugal"],
            default=["🇫🇷 France"],
            help="Sélectionner les pays à afficher"
        )
        
        # Color coding options
        checkbox_choix_couleur = st.radio(
            "Colorer les marqueurs selon",
            ["🏄‍♂️ Prévisions", "⏱️ Distance", "💶 Prix"],
            help="Choisir le critère de coloration des marqueurs"
        )
    
    # Single expander for both legend and guide
    with st.expander("ℹ️ Guide et légende", expanded=False):
        st.markdown("""
        La carte interactive affiche votre position actuelle (🏠) et les spots de surf à proximité (🚩). 
        Chaque spot est marqué d'un point coloré indiquant la qualité attendue du surf :
        - 🟢 Vert : Conditions idéales avec des vagues propres et puissantes
        - 🟡 Jaune : Conditions surfables mais moins constantes ou légèrement agitées
        - 🔴 Rouge : Conditions défavorables (vent fort, marées inadaptées, risques)
        
        Cliquez sur n'importe quel marqueur pour voir les informations détaillées sur :
        - La marée
        - Le vent
        - La compatibilité de la houle
        - Les prévisions détaillées
        """)
    
    return address, True, option_forecast, option_prix, option_distance_h, selectbox_daily_forecast, multiselect_pays, checkbox_choix_couleur

def create_suggestions_section(forecasts, selected_day):
    """Create a section for surf spot suggestions."""
    st.markdown("### 🏄‍♂️ Suggestions de spots")
    
    if not forecasts:
        st.warning("Aucun spot trouvé pour vos critères")
        return
        
    # Sort spots by rating for the selected day
    sorted_spots = sorted(
        forecasts,
        key=lambda x: x.get('forecast', [{}])[0].get('daily_rating', 0) if x.get('forecast') else 0,
        reverse=True
    )
    
    # Take top 3 spots
    top_spots = sorted_spots[:3]
    
    # Create columns for spot cards
    cols = st.columns(3)
    
    for i, spot in enumerate(top_spots):
        with cols[i]:
            forecast = spot.get('forecast', [{}])[0] if spot.get('forecast') else {}
            wave_height = forecast.get('wave_height_m', {})
            rating = forecast.get('daily_rating', 0)
            distance = spot.get('distance_km', 0)
            
            st.markdown(f"""
            <div style='padding: 20px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;'>
                <h4>{spot.get('name', 'Unknown Spot')}</h4>
                <p>Match: {rating:.0f}/10</p>
                <p>🌊 {wave_height.get('min', 0)}-{wave_height.get('max', 0)}m</p>
                <p>⏱️ {distance:.1f} km</p>
            </div>
            """, unsafe_allow_html=True)

def add_spot_markers(m, forecasts, selected_day, color_by, max_time=0, max_cost=0, min_rating=0):
    """Add markers for surf spots to the map."""
    try:
        logger.info(f"Starting to add markers for {len(forecasts)} spots")
        
        # Create a marker cluster
        marker_cluster = MarkerCluster().add_to(m)
        markers_added = 0
        
        # Process each spot
        for spot in forecasts:
            try:
                # Extract spot information
                spot_name = spot.get('name', 'Unknown Spot')
                latitude = spot.get('latitude')
                longitude = spot.get('longitude')
                
                if not latitude or not longitude:
                    logger.warning(f"Missing coordinates for {spot_name}")
                    continue
                
                # Get forecast for selected day
                forecast = spot.get('forecast', [{}])[0] if spot.get('forecast') else {}
                rating = forecast.get('daily_rating', 0)
                distance = spot.get('distance_km', 0)
                
                # Apply filters
                if rating < min_rating:
                    continue
                    
                # Determine marker color based on selected criteria
                if color_by == "🏄‍♂️ Prévisions":
                    color = displaymap_config.color_rating_forecast(rating)
                elif color_by == "⏱️ Distance":
                    color = displaymap_config.color_rating_distance(distance / 60)  # Convert km to hours
                else:  # "💶 Prix"
                    cost = distance * 0.15  # Rough estimate of cost per km
                    color = displaymap_config.color_rating_distance(cost / 20)  # Scale cost to 0-10
                
                # Create popup content
                wave_height = forecast.get('wave_height_m', {})
                wind_speed = forecast.get('wind_speed_m_s', 0)
                wind_direction = forecast.get('wind_direction', 'Unknown')
                tide_state = forecast.get('tide_state', 'Unknown')
                
                popup_content = f"""
                <div style='width: 300px; max-height: 400px; overflow-y: auto;'>
                    <h4>{spot_name}</h4>
                    <p><strong>Region:</strong> {spot.get('region', 'Unknown')}</p>
                    <p><strong>Type:</strong> {spot.get('type', 'Unknown')}</p>
                    <p><strong>Best Season:</strong> {spot.get('best_season', 'Unknown')}</p>
                    <hr>
                    <h5>Current Conditions:</h5>
                    <p>🌊 Wave Height: {wave_height.get('min', 0)}-{wave_height.get('max', 0)}m</p>
                    <p>💨 Wind: {wind_speed}m/s {wind_direction}</p>
                    <p>🌊 Tide: {tide_state}</p>
                    <p>⭐ Rating: {rating}/10</p>
                    <p>📍 Distance: {distance:.1f}km</p>
                </div>
                """
                
                # Create and add marker
                folium.Marker(
                    location=[latitude, longitude],
                    popup=folium.Popup(popup_content, max_width=300),
                    icon=folium.Icon(color=color, icon='info-sign'),
                ).add_to(marker_cluster)
                
                markers_added += 1
                
            except Exception as e:
                logger.error(f"Error processing spot {spot.get('name', 'unknown')}: {str(e)}")
                continue
        
        logger.info(f"Successfully added {markers_added} markers to the map")
        
    except Exception as e:
        logger.error(f"Error adding spot markers: {str(e)}")
        return

def main():
    """Main application function."""
    # Get forecast days
    day_list = forecast_config.get_dayList_forecast()
    
    # Initialize session states if not exists
    if 'forecasts' not in st.session_state:
        st.session_state.forecasts = None
    if 'surf_spots_data' not in st.session_state:
        st.session_state.surf_spots_data = None
    if 'uploaded_file' not in st.session_state:
        st.session_state.uploaded_file = None
    
    # File uploader in sidebar
    with st.sidebar:
        st.header("Data Configuration")
        uploaded_file = st.file_uploader("Upload custom surf spots data (JSON)", type=['json'])
        
        # Handle file upload changes
        if uploaded_file is not None and uploaded_file != st.session_state.uploaded_file:
            logger.info("New file uploaded, clearing session state")
            st.session_state.uploaded_file = uploaded_file
            st.session_state.surf_spots_data = None
            st.session_state.forecasts = None
        elif uploaded_file is None and st.session_state.uploaded_file is not None:
            logger.info("File removed, clearing session state")
            st.session_state.uploaded_file = None
            st.session_state.surf_spots_data = None
            st.session_state.forecasts = None
    
    # Create responsive layout and get inputs
    (address, validation_button, option_forecast, option_prix, 
     option_distance_h, selectbox_daily_forecast, multiselect_pays, checkbox_choix_couleur) = create_responsive_layout(day_list)
    
    # Get user's location
    user_location = get_user_location()
    
    # Process location and load data
    if address:
        coordinates = None
        if user_location:
            coordinates = user_location
        else:
            coordinates = forecast_config.get_coordinates(address)
            
        if coordinates:
            # Initialize map centered on the location
            m = folium.Map(location=coordinates, zoom_start=12)
            
            # Add user location marker
            folium.Marker(
                coordinates,
                popup='Your Location',
                icon=folium.Icon(color='red', icon='home')
            ).add_to(m)
            
            # Load and process forecasts
            if st.session_state.forecasts is None:
                with st.spinner('Loading surf spots...'):
                    forecasts = forecast_config.load_forecast_data(
                        address=address,
                        day_list=day_list,
                        coordinates=coordinates,
                        file_obj=st.session_state.uploaded_file
                    )
                    st.session_state.forecasts = forecasts
            
            if st.session_state.forecasts:
                # Add spot markers
                add_spot_markers(
                    m=m,
                    forecasts=st.session_state.forecasts,
                    selected_day=selectbox_daily_forecast,
                    color_by=checkbox_choix_couleur,
                    max_time=option_distance_h,
                    max_cost=option_prix,
                    min_rating=option_forecast
                )
                
                # Add map controls
                plugins.Fullscreen().add_to(m)
                Draw().add_to(m)
                
                # Display the map
                st_data = st_folium(m, width=1200, height=600)
                
                # Create suggestions section
                create_suggestions_section(st.session_state.forecasts, selectbox_daily_forecast)
            else:
                st.error("No surf spots found. Please check your data file or try a different location.")
        else:
            st.error("Could not determine location coordinates. Please try a different address.")

if __name__ == "__main__":
    main()
