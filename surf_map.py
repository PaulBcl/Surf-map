#!/usr/bin/env python
# coding: utf-8

import streamlit as st

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
from surfmap_config import forecast_config
import logging

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
        return None

def create_responsive_layout(day_list):
    """Create a responsive layout for the application."""
    # Create containers for different sections
    header_container = st.container()
    filters_container = st.container()
    map_container = st.container()
    suggestions_container = st.container()
    footer_container = st.container()
    
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
    
    # Single expander for both legend and guide
    with st.expander("ℹ️ Guide et légende", expanded=False):
        st.markdown("""
        La carte interactive affiche votre position actuelle (🏠) et les spots de surf à proximité (🚩). Chaque spot est marqué d'un point coloré indiquant la qualité attendue du surf : vert (🟢) pour des conditions idéales avec des vagues propres et puissantes ; jaune (🟡) pour des conditions surfables mais moins constantes ou légèrement agitées ; et rouge (🔴) lorsque les conditions sont défavorables, comme en cas de vent fort, de marées inadaptées ou de risques pour la sécurité. Cliquez sur n'importe quel marqueur pour voir les informations détaillées sur la marée, le vent et la compatibilité de la houle de ce spot. Ce système vous aide à évaluer rapidement quels spots méritent d'être visités près de chez vous, vous faisant gagner du temps et rendant la planification de vos sessions sans effort.
        """)
    
    # Return values including the address
    validation_button = True  # Always true since we're using geolocation
    option_forecast = 0
    option_prix = 0
    option_distance_h = 0
    multiselect_pays = ["🇫🇷 France"]  # Default to France
    checkbox_choix_couleur = "🏄‍♂️ Prévisions"
    
    return address, validation_button, option_forecast, option_prix, option_distance_h, selectbox_daily_forecast, multiselect_pays, checkbox_choix_couleur

def create_suggestions_section():
    """Create a placeholder section for surf spot suggestions."""
    st.markdown("### 🏄‍♂️ Suggestions de spots")
    
    # Create a grid of suggestion cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style='padding: 20px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;'>
            <h4>Spot 1</h4>
            <p>Match: 95%</p>
            <p>🌊 2-3m</p>
            <p>⏱️ 2h30</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='padding: 20px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;'>
            <h4>Spot 2</h4>
            <p>Match: 88%</p>
            <p>🌊 1-2m</p>
            <p>⏱️ 1h45</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='padding: 20px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px;'>
            <h4>Spot 3</h4>
            <p>Match: 82%</p>
            <p>🌊 1-1.5m</p>
            <p>⏱️ 3h15</p>
        </div>
        """, unsafe_allow_html=True)

def add_spot_markers(m, forecasts, selected_day, color_by, max_time=0, max_cost=0, min_rating=0):
    """
    Add markers for surf spots to the map.
    
    Args:
        m: folium Map object
        forecasts: List of surf spot forecasts
        selected_day: Selected day for forecasts
        color_by: What to color the markers by ('rating', 'time', or 'cost')
        max_time: Maximum travel time filter (0 for no filter)
        max_cost: Maximum cost filter (0 for no filter)
        min_rating: Minimum rating filter
    """
    try:
        # Create a marker cluster
        marker_cluster = MarkerCluster().add_to(m)
        
        # Create an expander for logging messages
        with st.expander("Debug Logs", expanded=False):
            st.write(f"Processing {len(forecasts)} spots...")
        
        # Process each spot
        for spot in forecasts:
            try:
                # Extract spot information
                spot_info = spot
                spot_name = spot_info['name']
                spot_lat = float(spot_info['latitude'])
                spot_lon = float(spot_info['longitude'])
                distance = float(spot_info['distance_km'])
                rating = float(spot_info['average_rating'])
                
                # Get the forecast for the selected day
                spot_forecast = next((f for f in spot_info['forecast'] if f['date']), None)
                if spot_forecast:
                    daily_rating = float(spot_forecast['daily_rating'])
                else:
                    daily_rating = 0.0
                
                # Calculate travel time (rough estimate: 60 km/h average speed)
                travel_time = distance / 60  # Convert to hours
                
                # Calculate cost (rough estimate: 0.5€/km)
                travel_cost = distance * 0.5
                
                # Apply filters
                if max_time > 0 and travel_time > max_time:
                    continue
                if max_cost > 0 and travel_cost > max_cost:
                    continue
                if daily_rating < min_rating:
                    continue
                
                # Determine marker color based on selection
                if color_by == "🏄‍♂️ Prévisions":
                    # Color based on rating
                    if daily_rating >= 8:
                        color = 'darkgreen'
                    elif daily_rating >= 6:
                        color = 'green'
                    elif daily_rating >= 4:
                        color = 'orange'
                    else:
                        color = 'red'
                elif color_by == "⏱️ Temps de trajet":
                    # Color based on travel time
                    if max_time == 0:  # Use absolute scale
                        if travel_time <= 2:
                            color = 'darkgreen'
                        elif travel_time <= 4:
                            color = 'green'
                        elif travel_time <= 6:
                            color = 'orange'
                        else:
                            color = 'red'
                    else:  # Use relative scale
                        if travel_time <= max_time * 0.25:
                            color = 'darkgreen'
                        elif travel_time <= max_time * 0.5:
                            color = 'green'
                        elif travel_time <= max_time * 0.75:
                            color = 'orange'
                        else:
                            color = 'red'
                else:  # "💶 Coût"
                    # Color based on cost
                    if max_cost == 0:  # Use absolute scale
                        if travel_cost <= 20:
                            color = 'darkgreen'
                        elif travel_cost <= 50:
                            color = 'green'
                        elif travel_cost <= 80:
                            color = 'orange'
                        else:
                            color = 'red'
                    else:  # Use relative scale
                        if travel_cost <= max_cost * 0.25:
                            color = 'darkgreen'
                        elif travel_cost <= max_cost * 0.5:
                            color = 'green'
                        elif travel_cost <= max_cost * 0.75:
                            color = 'orange'
                        else:
                            color = 'red'
                
                # Create popup content
                popup_content = f"""
                <div style='min-width: 300px'>
                    <h4>{spot_name}</h4>
                    <p><b>Region:</b> {spot_info['region']}</p>
                    <p><b>Type:</b> {spot_info['type']}</p>
                    <p><b>Distance:</b> {distance:.1f} km</p>
                    <p><b>Temps de trajet estimé:</b> {travel_time:.1f}h</p>
                    <p><b>Coût estimé:</b> {travel_cost:.2f}€</p>
                    <p><b>Note:</b> {daily_rating}/10</p>
                    <hr>
                    <p><b>Best Season:</b> {spot_info['best_season']}</p>
                    <p><b>Difficulty:</b> {', '.join(spot_info['difficulty'])}</p>
                    <p><b>Orientation:</b> {spot_info['orientation']}</p>
                    <p><b>Wave Description:</b> {spot_info['wave_description']}</p>
                    <hr>
                    <p><b>Current Conditions:</b></p>
                    <p><b>Vagues:</b> {spot_forecast['wave_height_m']['min']}-{spot_forecast['wave_height_m']['max']}m</p>
                    <p><b>Période:</b> {spot_forecast['wave_period_s']}s</p>
                    <p><b>Vent:</b> {spot_forecast['wind_speed_m_s']}m/s {spot_forecast['wind_direction']}</p>
                    <hr>
                    <p><b>Local Tips:</b> {spot_info['local_tips']}</p>
                    <p><b>Access:</b> {spot_info['access']}</p>
                    <p><b>Gear Rental:</b> {spot_info['gear_rental']}</p>
                    <p><b>Nearby Lodging:</b> {spot_info['nearby_lodging']}</p>
                    <hr>
                    <p><b>Forecast Links:</b></p>
                    {''.join(f'<a href="{link}" target="_blank">Forecast {i+1}</a><br>' for i, link in enumerate(spot_info['surf_forecast_link']))}
                </div>
                """
                
                # Add marker to cluster
                folium.Marker(
                    location=[spot_lat, spot_lon],
                    popup=folium.Popup(popup_content, max_width=300),
                    icon=folium.Icon(color=color, icon='info-sign')
                ).add_to(marker_cluster)
                
            except Exception as e:
                with st.expander("Debug Logs", expanded=False):
                    st.error(f"Error processing spot {spot_name}: {str(e)}")
                continue
        
        return marker_cluster
    except Exception as e:
        st.error(f"Error adding markers: {str(e)}")
        return None

def main():
    """Main application function."""
    # Get forecast days
    day_list = forecast_config.get_dayList_forecast()
    
    # Initialize session state for forecasts if not exists
    if 'forecasts' not in st.session_state:
        st.session_state.forecasts = None
    
    # Create responsive layout and get inputs
    (address, validation_button, option_forecast, option_prix, 
     option_distance_h, selectbox_daily_forecast, multiselect_pays, checkbox_choix_couleur) = create_responsive_layout(day_list)
    
    # Get user's location
    user_location = get_user_location()
    
    # Handle location logic
    if user_location:
        # Use browser geolocation
        base_position = user_location
        st.session_state.forecasts = forecast_config.load_forecast_data(coordinates=user_location)
    elif address:
        # Use manually entered address with Google Maps geocoding
        try:
            from surfmap_config import api_config
            geocode_result = api_config.get_google_results(address, api_config.gmaps_api_key)
            logger.info(f"Geocode result: {geocode_result}")  # Debug log
            
            if geocode_result and geocode_result.get('success'):
                base_position = [geocode_result['latitude'], geocode_result['longitude']]
                logger.info(f"Setting base position to: {base_position}")  # Debug log
                
                try:
                    st.session_state.forecasts = forecast_config.load_forecast_data(coordinates=base_position)
                    st.success(f"📍 Position trouvée : {geocode_result['formatted_address']}")
                except Exception as forecast_error:
                    logger.error(f"Error loading forecast data: {forecast_error}")  # Debug log
                    st.error(f"❌ Erreur lors du chargement des prévisions: {str(forecast_error)}")
                    base_position = [geocode_result['latitude'], geocode_result['longitude']]  # Still use the geocoded position
            else:
                error_msg = geocode_result.get('error_message', 'Unknown error') if geocode_result else 'No result'
                logger.error(f"Geocoding failed: {error_msg}")  # Debug log
                base_position = [46.603354, 1.888334]  # Center of France
                st.error("❌ Adresse non trouvée. Veuillez vérifier votre saisie.")
        except Exception as e:
            logger.error(f"Exception in geocoding: {str(e)}")  # Debug log
            base_position = [46.603354, 1.888334]  # Center of France
            st.error(f"❌ Erreur lors de la géolocalisation: {str(e)}")
    else:
        # No location available
        base_position = [46.603354, 1.888334]  # Center of France
        st.warning("❌ Impossible d'accéder à votre position. Veuillez entrer votre position manuellement ou vérifier les permissions de votre navigateur.")
    
    # Initialize map with user's position
    logger.info(f"Initializing map with position: {base_position}")  # Debug log
    m = folium.Map(location=base_position, zoom_start=8)
    
    # Add map controls
    MiniMap(toggle_display=True).add_to(m)
    Draw().add_to(m)
    
    # If we have forecasts, display them
    if st.session_state.forecasts:
        try:
            # Add home marker
            folium.Marker(
                location=base_position,
                popup=folium.Popup("🏠 Votre position", max_width=150),
                icon=folium.Icon(color='blue', icon='home')
            ).add_to(m)
            
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
            
            # Add suggestions section before the map
            st.markdown("---")
            create_suggestions_section()
            st.markdown("---")
            
            st.success(f"Found {len(st.session_state.forecasts)} surf spots near your location")
        except Exception as e:
            logger.error(f"Error processing map data: {str(e)}")  # Debug log
            st.error(f"Error processing data: {str(e)}")
    
    # Display the map in the map container
    with st.container():
        st.components.v1.html(m._repr_html_(), height=600)
    
    # Add footer
    st.markdown("---")
    st.markdown("Made with ❤️ by surf enthusiasts")

if __name__ == "__main__":
    main()
