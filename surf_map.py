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
    """
    try:
        logger.info(f"Starting to add markers for {len(forecasts)} spots")
        logger.info(f"Parameters: selected_day={selected_day}, color_by={color_by}, max_time={max_time}, max_cost={max_cost}, min_rating={min_rating}")
        
        # Create a marker cluster
        marker_cluster = MarkerCluster().add_to(m)
        markers_added = 0
        
        # Convert selected_day to the format used in forecasts (YYYY-MM-DD)
        try:
            # Parse the date from format "Day DD" (e.g., "Monday 15")
            current_year = datetime.now().year
            current_month = datetime.now().month
            day_num = int(selected_day.split()[1])
            # If the day number is less than today's day, it's next month
            if day_num < datetime.now().day:
                if current_month == 12:
                    current_month = 1
                    current_year += 1
                else:
                    current_month += 1
            forecast_date = datetime(current_year, current_month, day_num).strftime('%Y-%m-%d')
            logger.info(f"Converted selected_day '{selected_day}' to forecast date format: {forecast_date}")
        except Exception as e:
            logger.error(f"Error converting date format: {str(e)}")
            forecast_date = selected_day
        
        # Process each spot
        for spot in forecasts:
            try:
                # Extract spot information
                spot_info = spot
                spot_name = spot_info.get('name', 'Unknown Spot')
                distance = spot_info.get('distance_km', 0)
                travel_time = distance / 60  # Rough estimate: 60 km/h average speed
                
                # Find the forecast for the selected day
                daily_forecast = None
                if 'forecast' in spot_info:
                    for day_forecast in spot_info['forecast']:
                        if day_forecast.get('date') == forecast_date:
                            daily_forecast = day_forecast
                            break
                
                if not daily_forecast:
                    logger.warning(f"No forecast found for {spot_name} on {forecast_date}")
                    continue
                
                # Get the rating for the day
                rating = daily_forecast.get('daily_rating', 0)
                if rating < min_rating:
                    logger.info(f"Skipping {spot_name} due to low rating: {rating}")
                    continue
                
                # Skip if travel time exceeds max_time (if specified)
                if max_time > 0 and travel_time > max_time:
                    logger.info(f"Skipping {spot_name} due to travel time: {travel_time}h > {max_time}h")
                    continue
                
                # Calculate travel cost (rough estimate)
                fuel_cost_per_km = 0.15  # €/km
                toll_cost = distance * 0.10  # Rough estimate for toll costs
                travel_cost = (distance * fuel_cost_per_km) + toll_cost
                
                # Skip if travel cost exceeds max_cost (if specified)
                if max_cost > 0 and travel_cost > max_cost:
                    logger.info(f"Skipping {spot_name} due to travel cost: {travel_cost}€ > {max_cost}€")
                    continue
                
                # Determine marker color based on selected criteria
                if color_by == 'rating':
                    color = 'lightgray'
                    if rating >= 7:
                        color = 'darkgreen'
                    elif rating >= 5:
                        color = 'green'
                    elif rating >= 3:
                        color = 'orange'
                    elif rating > 0:
                        color = 'red'
                
                elif color_by == 'travel_time':
                    if max_time == 0:  # Use absolute scale
                        if travel_time <= 1:
                            color = 'darkgreen'
                        elif travel_time <= 2:
                            color = 'green'
                        elif travel_time <= 3:
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
                
                else:  # color_by == 'cost'
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
                
                logger.info(f"Adding marker for {spot_name} with color {color}")
                
                # Create popup content with error handling
                try:
                    wave_height = daily_forecast.get('wave_height_m', {})
                    wave_height_str = f"{wave_height.get('min', 0)}-{wave_height.get('max', 0)}m"
                    
                    popup_content = f"""
                    <div style='min-width: 300px'>
                        <h4>{spot_name}</h4>
                        <p><b>Region:</b> {spot_info.get('region', 'N/A')}</p>
                        <p><b>Type:</b> {spot_info.get('type', 'N/A')}</p>
                        <p><b>Distance:</b> {distance:.1f} km</p>
                        <p><b>Travel Time:</b> {travel_time:.1f}h</p>
                        <p><b>Travel Cost:</b> {travel_cost:.2f}€</p>
                        <p><b>Wave Height:</b> {wave_height_str}</p>
                        <p><b>Wave Period:</b> {daily_forecast.get('wave_period_s', 'N/A')}s</p>
                        <p><b>Wind Speed:</b> {daily_forecast.get('wind_speed_m_s', 'N/A')}m/s</p>
                        <p><b>Wind Direction:</b> {daily_forecast.get('wind_direction', 'N/A')}</p>
                        <p><b>Tide State:</b> {daily_forecast.get('tide_state', 'N/A')}</p>
                        <p><b>Rating:</b> {rating}/10</p>
                    </div>
                    """
                    
                    # Create marker with popup
                    folium.Marker(
                        location=[float(spot_info['latitude']), float(spot_info['longitude'])],
                        popup=folium.Popup(popup_content, max_width=300),
                        icon=folium.Icon(color=color, icon='info-sign'),
                    ).add_to(marker_cluster)
                    
                    markers_added += 1
                    
                except Exception as e:
                    logger.error(f"Error creating popup for {spot_name}: {str(e)}")
                    continue
                
            except Exception as e:
                logger.error(f"Error processing spot: {str(e)}")
                continue
        
        logger.info(f"Successfully added {markers_added} markers to the map")
        return markers_added
        
    except Exception as e:
        logger.error(f"Error in add_spot_markers: {str(e)}")
        return 0

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
    
    # Debug logging for location
    logger.info(f"User location: {user_location}")
    logger.info(f"Address entered: {address}")
    
    # Handle location logic
    if user_location:
        # Use browser geolocation
        base_position = user_location
        logger.info(f"Using browser geolocation: {base_position}")
        st.session_state.forecasts = forecast_config.load_forecast_data(coordinates=user_location)
        logger.info(f"Loaded {len(st.session_state.forecasts) if st.session_state.forecasts else 0} forecasts from geolocation")
    elif address:
        # Use manually entered address with Google Maps geocoding
        try:
            from surfmap_config import api_config
            geocode_result = api_config.get_google_results(address, api_config.gmaps_api_key)
            logger.info(f"Geocode result: {geocode_result}")
            
            if geocode_result and geocode_result.get('success'):
                base_position = [geocode_result['latitude'], geocode_result['longitude']]
                logger.info(f"Setting base position to: {base_position}")
                
                try:
                    # Load forecasts with coordinates
                    st.session_state.forecasts = forecast_config.load_forecast_data(coordinates=base_position)
                    logger.info(f"Loaded {len(st.session_state.forecasts) if st.session_state.forecasts else 0} forecasts")
                    
                    # Debug log the first forecast if available
                    if st.session_state.forecasts and len(st.session_state.forecasts) > 0:
                        logger.info(f"First forecast: {st.session_state.forecasts[0]}")
                    
                    st.success(f"📍 Position trouvée : {geocode_result['formatted_address']}")
                except Exception as forecast_error:
                    logger.error(f"Error loading forecast data: {forecast_error}")
                    st.error(f"❌ Erreur lors du chargement des prévisions: {str(forecast_error)}")
                    base_position = [geocode_result['latitude'], geocode_result['longitude']]
            else:
                error_msg = geocode_result.get('error_message', 'Unknown error') if geocode_result else 'No result'
                logger.error(f"Geocoding failed: {error_msg}")
                base_position = [46.603354, 1.888334]  # Center of France
                st.error("❌ Adresse non trouvée. Veuillez vérifier votre saisie.")
        except Exception as e:
            logger.error(f"Exception in geocoding: {str(e)}")
            base_position = [46.603354, 1.888334]  # Center of France
            st.error(f"❌ Erreur lors de la géolocalisation: {str(e)}")
    else:
        # No location available
        base_position = [46.603354, 1.888334]  # Center of France
        st.warning("❌ Impossible d'accéder à votre position. Veuillez entrer votre position manuellement ou vérifier les permissions de votre navigateur.")
    
    # Initialize map with user's position
    logger.info(f"Initializing map with position: {base_position}")
    m = folium.Map(location=base_position, zoom_start=8)
    
    # Add map controls
    MiniMap(toggle_display=True).add_to(m)
    Draw().add_to(m)
    
    # Debug log before adding markers
    logger.info(f"Forecasts in session state: {bool(st.session_state.forecasts)}")
    if st.session_state.forecasts:
        logger.info(f"Number of forecasts: {len(st.session_state.forecasts)}")
    
    # If we have forecasts, display them
    if st.session_state.forecasts:
        try:
            # Add home marker
            folium.Marker(
                location=base_position,
                popup=folium.Popup("🏠 Votre position", max_width=150),
                icon=folium.Icon(color='blue', icon='home')
            ).add_to(m)
            
            # Debug log before adding spot markers
            logger.info(f"Adding spot markers for {len(st.session_state.forecasts)} spots")
            logger.info(f"Selected day: {selectbox_daily_forecast}")
            logger.info(f"Color by: {checkbox_choix_couleur}")
            
            # Add spot markers
            markers_added = add_spot_markers(
                m=m,
                forecasts=st.session_state.forecasts,
                selected_day=selectbox_daily_forecast,
                color_by=checkbox_choix_couleur,
                max_time=option_distance_h,
                max_cost=option_prix,
                min_rating=option_forecast
            )
            
            # Debug log after adding markers
            logger.info(f"Markers added: {markers_added}")
            
            # Add suggestions section before the map
            st.markdown("---")
            create_suggestions_section()
            st.markdown("---")
            
            st.success(f"Found {len(st.session_state.forecasts)} surf spots near your location")
        except Exception as e:
            logger.error(f"Error processing map data: {str(e)}")
            st.error(f"Error processing data: {str(e)}")
    
    # Display the map in the map container
    with st.container():
        st.components.v1.html(m._repr_html_(), height=600)
    
    # Add footer
    st.markdown("---")
    st.markdown("Made with ❤️ by surf enthusiasts")

if __name__ == "__main__":
    main()
