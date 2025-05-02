#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pydeck as pdk
from streamlit_folium import st_folium

# Set page config - MUST BE FIRST STREAMLIT COMMAND
st.set_page_config(
    page_title="🌴 SurfMap",
    page_icon="🏄‍♂️",
    layout="wide"
)


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
import math

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a session state for the reset functionality
if 'run_id' not in st.session_state:
    st.session_state.run_id = 0

# Default map view settings
DEFAULT_LATITUDE = 48.8566
DEFAULT_LONGITUDE = 2.3522
DEFAULT_ZOOM = 12
DEFAULT_PITCH = 0
DEFAULT_BEARING = 0

def get_spot_color(rating):
    """Get color for spot based on rating."""
    if rating >= 8:  # Best spots (green)
        return [46, 204, 113, 200]
    elif rating >= 6:  # Good spots (yellow-green)
        return [241, 196, 15, 200]
    elif rating >= 4:  # Average spots (orange)
        return [230, 126, 34, 200]
    else:  # Poor spots (red)
        return [231, 76, 60, 200]

def create_pydeck_map(forecasts, user_lat=DEFAULT_LATITUDE, user_lon=DEFAULT_LONGITUDE):
    """Create a PyDeck map with surf spots."""
    try:
        # Sort forecasts by rating to identify top 3
        sorted_forecasts = sorted(
            forecasts,
            key=lambda x: float(x.get('forecast', [{}])[0].get('daily_rating', 0) if x.get('forecast') else 0),
            reverse=True
        )
        top_3_names = [spot['name'] for spot in sorted_forecasts[:3]]
        
        # Prepare data for PyDeck
        map_data = []
        lats = []
        lons = []
        
        for spot in forecasts:
            forecast = spot.get('forecast', [{}])[0] if spot.get('forecast') else {}
            
            # Log warnings for missing data
            if not forecast.get('daily_rating'):
                logger.warning(f"Missing daily_rating for spot: {spot.get('name')}")
            if not forecast.get('summary'):
                logger.warning(f"Missing summary for spot: {spot.get('name')}")
            
            lat = float(spot.get('latitude', 0))
            lon = float(spot.get('longitude', 0))
            lats.append(lat)
            lons.append(lon)
            
            map_data.append({
                'name': spot.get('name', 'Unknown Spot'),
                'latitude': lat,
                'longitude': lon,
                'region': spot.get('region', 'Unknown'),
                'type': spot.get('type', 'Unknown'),
                'forecast': forecast
            })
        
        # Calculate center and bounds
        center_lat = sum(lats) / len(lats) if lats else user_lat
        center_lon = sum(lons) / len(lons) if lons else user_lon
        
        # Calculate zoom level based on bounds
        lat_diff = max(lats) - min(lats) if lats else 0
        lon_diff = max(lons) - min(lons) if lons else 0
        
        # Adjust zoom calculation for better visibility
        zoom = min(
            11,  # Max zoom out
            max(
                8,  # Min zoom out
                round(
                    min(
                        -math.log2(lat_diff) + 9.5,
                        -math.log2(lon_diff) + 9.5
                    )
                )
            )
        ) if lat_diff and lon_diff else DEFAULT_ZOOM
        
        # Create DataFrame for PyDeck
        df = pd.DataFrame(map_data)
        
        # Create the scatter plot layer
        layer = pdk.Layer(
            'ScatterplotLayer',
            data=df,
            get_position=['longitude', 'latitude'],
            get_fill_color="""
                [forecast[0].daily_rating >= 7.5 ? 0 : forecast[0].daily_rating >= 6 ? 255 : 200,
                 forecast[0].daily_rating >= 7.5 ? 200 : 140,
                 forecast[0].daily_rating >= 7.5 ? 0 : 0]
            """,
            get_radius="forecast[0].daily_rating * 2000",
            pickable=True,
            opacity=0.8,
            stroked=True,
            filled=True,
            line_width_min_pixels=3,
            line_width_scale=2,
            get_line_color=[255, 255, 255, 200],  # White border
        )
        
        # Create the view state with calculated values
        view_state = pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=zoom,
            pitch=0,
            bearing=0
        )
        
        # Create the deck
        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style="mapbox://styles/mapbox/outdoors-v12",
            tooltip={
                "html": "<b>{name}</b><br>Rating: {forecast[0].daily_rating}/10<br>{forecast[0].summary}",
                "style": {
                    "backgroundColor": "white",
                    "color": "black",
                    "fontSize": "12px"
                }
            }
        )
        
        return deck
        
    except Exception as e:
        logger.error(f"Error creating PyDeck map: {str(e)}")
        return None

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
        # Store both formats: one for display and one for data processing
        selectbox_daily_forecast = {
            'display': selected_date.strftime('%A %d').replace('0', ' ').lstrip(),
            'value': selected_date.strftime('%Y-%m-%d')
        }
    
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
        key=lambda x: (
            float(x.get('forecast', [{}])[0].get('daily_rating', 0))
            if x.get('forecast') and x['forecast'][0].get('daily_rating') is not None
            else float(x.get('match', 0))
            if x.get('match') is not None
            else 0
        ),
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
        quick_summary = forecast.get('quick_summary', 'Summary not available')
        
        with st.container():
            # Style the container with CSS
            st.markdown("""
                <style>
                    div[data-testid="stVerticalBlock"]:has(> div.spot-container) {
                        background-color: #f0f2f6;
                        padding: 20px;
                        border-radius: 10px;
                        margin-bottom: 20px;
                    }
                </style>
                <div class="spot-container"></div>
            """, unsafe_allow_html=True)
            
            # Spot name
            st.markdown(f"### {spot.get('name', 'Unknown Spot')}")
            
            # Executive Summary
            st.markdown("""
                <div style='background-color: #e8f4f8; padding: 15px; border-radius: 8px; margin-bottom: 15px;'>
                    🌊 **Surf Summary**: {summary}
                </div>
            """.format(
                summary=(
                    spot["forecast"][0].get("summary")
                    or spot["forecast"][0].get("quick_summary")
                    or "⚠️ GPT returned no summary for this spot."
                ) if spot.get("forecast") else "⚠️ GPT returned no summary for this spot."
            ), unsafe_allow_html=True)
            
            # Forecasted Conditions Block
            st.markdown(f"""
                - 🥇 **Match Rating**: {rating:.1f}/10  
                - 🌊 **Wave Height**: {wave_height.get('min', 0)}–{wave_height.get('max', 0)} m  
                - 🍃 **Wind**: {forecast.get('wind_direction', 'Unknown')} @ {forecast.get('wind_speed_m_s', 0)} m/s  
                - 🕑 **Tide**: {forecast.get('tide_state', 'Unknown').title()}  
                - 📍 **Distance**: {distance:.1f} km
            """)
            
            # Pro Analysis Section
            with st.expander("🔍 Pro Analysis"):
                if spot.get("forecast"):
                    analysis = (
                        spot["forecast"][0].get("analysis")
                        or spot["forecast"][0].get("conditions_analysis")
                        or "⚠️ No detailed analysis returned."
                    )
                    st.markdown(analysis)
                else:
                    st.write("⚠️ No detailed analysis returned.")
            
            st.markdown("---")
    
    # Display remaining spots with basic info only
    if len(sorted_spots) > 3:
        with st.expander("📍 Other Nearby Spots"):
            for spot in sorted_spots[3:8]:  # Only show next 5 spots
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
                    # Pass the selected date directly in YYYY-MM-DD format
                    forecasts = forecast_config.load_forecast_data(
                        address=address,
                        day_list=[selectbox_daily_forecast['value']],  # Use the full date
                        coordinates=[lat, lon]
                    )
                    st.session_state.forecasts = forecasts
                
                if st.session_state.forecasts:
                    # Create suggestions section first
                    create_suggestions_section(st.session_state.forecasts, selectbox_daily_forecast['display'])
                    
                    # Add map header
                    st.markdown("### 🗺️ Surf Spot Forecast Map")
                    
                    # Create and display PyDeck map
                    deck = create_pydeck_map(st.session_state.forecasts, lat, lon)
                    if deck:
                        st.pydeck_chart(deck)
                    else:
                        st.error("Error creating map visualization")
                else:
                    st.error("No surf spots found. Please try a different location.")
            except (ValueError, TypeError) as e:
                logger.error(f"Error processing coordinates: {str(e)}")
                st.error("Invalid coordinates received. Please try a different address.")
        else:
            st.error("Could not determine location coordinates. Please try a different address.")
    else:
        # Display default map centered on Paris
        if st.session_state.forecasts:
            st.markdown("### 🗺️ Surf Spot Forecast Map")
            deck = create_pydeck_map(st.session_state.forecasts)
            if deck:
                st.pydeck_chart(deck)

if __name__ == "__main__":
    main()
