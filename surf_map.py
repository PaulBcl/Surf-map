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

# Hide all Streamlit's default messages
st.set_option('server.showLoadingSpinner', False)
st.set_option('server.showWarning', False)
st.set_option('server.displaySpinnerDuringCachedFunction', False)  # Hide cache execution messages

# Hide "Running..." messages
st.cache_data.clear()
st.cache_resource.clear()

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

def create_responsive_layout(day_list):
    """Create a responsive layout for the application."""
    # Welcome block - full width, simplified
    st.markdown("""
    <div style='text-align: center; margin-bottom: 1.5rem;'>
        <h1 style='margin-bottom: 1rem; font-size: 1.8rem;'>Welcome to Surfmap! 🌊</h1>
    </div>
    """, unsafe_allow_html=True)
    
    # Create two columns for date selection and location input
    col1, col2 = st.columns(2)
    
    with col1:
        # Date selection with calendar
        st.markdown("#### 📅 Select your day")
        today = datetime.now()
        selected_date = st.date_input(
            "Choose a day for your forecast",
            min_value=today.date(),
            max_value=today.date() + timedelta(days=6),
            value=today.date(),
            format="DD/MM/YYYY"
        )
        # Convert the selected date to the format expected by the rest of the application
        selectbox_daily_forecast = selected_date.strftime('%A %d').replace('0', ' ').lstrip()
    
    with col2:
        # Location input
        st.markdown("#### 📍 Your location")
        address = st.text_input(
            "Enter your city or address",
            placeholder="ex: Lisbon, Portugal",
            help="If geolocation doesn't work, enter your location manually"
        )
    
    # Single expander for both legend and guide
    with st.expander("ℹ️ Guide and legend", expanded=False):
        st.markdown("""
        The interactive map shows your current location (🏠) and nearby surf spots (🚩). 
        Each spot is marked with a colored dot indicating the expected surf quality:
        - 🟢 Green: Ideal conditions with clean, powerful waves
        - 🟡 Yellow: Surfable conditions but less consistent or slightly choppy
        - 🔴 Red: Unfavorable conditions (strong winds, unsuitable tides, risks)
        
        Click on any marker to see detailed information about:
        - Tide
        - Wind
        - Swell compatibility
        - Detailed forecast
        """)
    
    return address, selectbox_daily_forecast

def create_suggestions_section(forecasts, selected_day):
    """Create a section for surf spot suggestions."""
    st.markdown("### 🏄‍♂️ Spot Suggestions")
    
    if not forecasts:
        st.warning("No spots found for your criteria")
        return
        
    # Sort spots by rating for the selected day
    sorted_spots = sorted(
        forecasts,
        key=lambda x: x.get('forecast', [{}])[0].get('daily_rating', 0) if x.get('forecast') else 0,
        reverse=True
    )
    
    # Create a container for top 3 spots
    with st.container():
        st.markdown("#### 🏆 Top Spots for Today")
        
        # Take top 3 spots
        top_spots = sorted_spots[:3]
        
        # Display each of the top 3 spots
        for spot in top_spots:
            forecast = spot.get('forecast', [{}])[0] if spot.get('forecast') else {}
            wave_height = forecast.get('wave_height_m', {})
            rating = forecast.get('daily_rating', 0)
            distance = spot.get('distance_km', 0)
            conditions_analysis = forecast.get('conditions_analysis', 'No analysis available')
            
            # Create the card with enhanced styling
            st.markdown(f"""
            <div style='padding: 20px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 20px; width: 100%;'>
                <h3>{spot.get('name', 'Unknown Spot')}</h3>
                <div style='display: flex; gap: 20px; margin-bottom: 10px;'>
                    <div><strong>Match:</strong> {rating:.0f}/10</div>
                    <div><strong>📍 Distance:</strong> {distance:.1f} km</div>
                </div>
                
                <!-- Quick Summary -->
                <div style='background-color: white; padding: 15px; border-radius: 5px; margin-bottom: 15px;'>
                    <p>🌬️ Wind: {forecast.get('wind_direction', 'Unknown')} @ {forecast.get('wind_speed_m_s', 0)} m/s</p>
                    <p>🌊 Waves: {wave_height.get('min', 0)}-{wave_height.get('max', 0)}m</p>
                    <p>🌊↘ Tide: {forecast.get('tide_state', 'Unknown').title()}</p>
                </div>
                
                <div style='margin-bottom: 15px;'>
                    <p><strong>Spot type:</strong> {spot.get('type', 'Unknown')}</p>
                    <p><strong>Best season:</strong> {spot.get('best_season', 'Unknown')}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Add Pro Analysis expander
            with st.expander("🔍 Pro Analysis"):
                st.markdown(conditions_analysis)
        
        # Add visual separator after top 3
        st.markdown("---")
        
    # Display remaining spots with basic info only
    if len(sorted_spots) > 3:
        st.markdown("#### Other Nearby Spots")
        for spot in sorted_spots[3:]:
            forecast = spot.get('forecast', [{}])[0] if spot.get('forecast') else {}
            rating = forecast.get('daily_rating', 0)
            distance = spot.get('distance_km', 0)
            
            st.markdown(f"""
            <div style='padding: 15px; border-radius: 10px; background-color: #f0f2f6; margin-bottom: 10px; width: 100%;'>
                <h4>{spot.get('name', 'Unknown Spot')}</h4>
                <div style='display: flex; gap: 20px;'>
                    <div><strong>Match:</strong> {rating:.0f}/10</div>
                    <div><strong>📍 Distance:</strong> {distance:.1f} km</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def add_spot_markers(m, forecasts, selected_day):
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
                
                # Color based on forecast rating
                color = displaymap_config.color_rating_forecast(rating)
                
                # Create popup content
                wave_height = forecast.get('wave_height_m', {})
                wind_speed = forecast.get('wind_speed_m_s', 0)
                wind_direction = forecast.get('wind_direction', 'Unknown')
                tide_state = forecast.get('tide_state', 'Unknown')
                conditions_analysis = forecast.get('conditions_analysis', 'No analysis available')
                
                popup_content = f"""
                <div style='width: 300px; max-height: 400px; overflow-y: auto;'>
                    <h4>{spot_name}</h4>
                    <div style='margin-bottom: 10px;'>
                        <strong>Rating:</strong> {rating}/10
                    </div>
                    <div style='margin-bottom: 15px;'>
                        <h5>Current Conditions:</h5>
                        <p>🌊 Waves: {wave_height.get('min', 0)}-{wave_height.get('max', 0)}m</p>
                        <p>💨 Wind: {wind_speed}m/s {wind_direction}</p>
                        <p>🌊 Tide: {tide_state}</p>
                        <p>📍 Distance: {distance:.1f}km</p>
                    </div>
                    <div style='margin-top: 15px;'>
                        <h5>Conditions Analysis:</h5>
                        <p style='font-size: 0.9em;'>{conditions_analysis}</p>
                    </div>
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
    
    # Initialize session state for forecasts if not exists
    if 'forecasts' not in st.session_state:
        st.session_state.forecasts = None
    
    # Create responsive layout and get inputs
    address, selectbox_daily_forecast = create_responsive_layout(day_list)
    
    # Process location and load data
    if address:
        # Get coordinates from address
        coordinates = forecast_config.get_coordinates(address)
        
        if coordinates and coordinates[0] is not None and coordinates[1] is not None:
            try:
                # Ensure coordinates are float values
                lat, lon = float(coordinates[0]), float(coordinates[1])
                
                # Load and process forecasts first
                if st.session_state.forecasts is None:
                    # Remove the spinner and let the progress bar from load_forecast_data handle the loading state
                    forecasts = forecast_config.load_forecast_data(
                        address=address,
                        day_list=day_list,
                        coordinates=[lat, lon]
                    )
                    st.session_state.forecasts = forecasts
                
                if st.session_state.forecasts:
                    # Create suggestions section first
                    create_suggestions_section(st.session_state.forecasts, selectbox_daily_forecast)
                    
                    # Initialize map centered on the location
                    m = folium.Map(location=[lat, lon], zoom_start=12)
                    
                    # Add user location marker
                    folium.Marker(
                        [lat, lon],
                        popup='Your Location',
                        icon=folium.Icon(color='red', icon='home')
                    ).add_to(m)
                    
                    # Add spot markers
                    add_spot_markers(
                        m=m,
                        forecasts=st.session_state.forecasts,
                        selected_day=selectbox_daily_forecast
                    )
                    
                    # Add map controls
                    plugins.Fullscreen().add_to(m)
                    Draw().add_to(m)
                    
                    # Display the map
                    st_data = st_folium(m, width=1200, height=600)
                else:
                    st.error("No surf spots found. Please try a different location.")
            except (ValueError, TypeError) as e:
                logger.error(f"Error processing coordinates: {str(e)}")
                st.error("Invalid coordinates received. Please try a different address.")
        else:
            st.error("Could not determine location coordinates. Please try a different address.")

if __name__ == "__main__":
    main()
