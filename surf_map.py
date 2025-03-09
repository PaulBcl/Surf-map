#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import folium
from folium import plugins
from folium.plugins import MarkerCluster, MiniMap, Draw
import pandas as pd
from datetime import datetime, timedelta
from surfmap_config import forecast_config

# Set page config
st.set_page_config(
    page_title="🏄‍♂️ SurfMap",
    page_icon="🏄‍♂️",
    layout="wide"
)

# Add app description and guide
st.title("🏄‍♂️ SurfMap - Find Your Perfect Wave")

# Main description in an expander
with st.expander("ℹ️ About SurfMap", expanded=True):
    st.markdown("""
    SurfMap helps you discover the best surf spots based on real-time conditions and your preferences. 
    Using advanced AI and multiple data sources, we analyze wave conditions, wind patterns, and local factors 
    to find perfect surf spots near you.
    
    ### 🎯 What Makes a Good Surf Spot?
    - **Wave Quality**: Height, period, and energy
    - **Wind Conditions**: Direction and speed
    - **Accessibility**: Distance and travel time
    - **Spot Characteristics**: Orientation and typical conditions
    """)

# Guide in an expander
with st.expander("📖 Guide d'Utilisation / User Guide", expanded=False):
    st.markdown("""
    ### How to Use SurfMap:
    
    1. **Enter Your Location** 🏠
       - Type your address or city in the sidebar
       - Click 'Search' to find nearby surf spots
    
    2. **Choose Your Day** 📅
       - Select which day you want to surf
       - We provide forecasts for the next 7 days
    
    3. **Adjust Filters** 📊
       - Set minimum acceptable wave rating
       - Define maximum travel time
       - Set your budget limit
    
    4. **Understand the Colors** 🎨
       Choose how to color the markers:
       
       **Wave Rating:**
       - 🟢 Dark Green = Excellent (7-10)
       - 🟡 Green = Good (5-7)
       - 🟠 Orange = Fair (3-5)
       - 🔴 Red = Poor (0-3)
       
       **Travel Time:**
       - Colors show relative distance to your max setting
       
       **Cost:**
       - Colors indicate expense relative to your budget
    """)

# Technical details in an expander
with st.expander("🔧 Technical Details", expanded=False):
    st.markdown("""
    ### How We Rate Surf Spots:
    
    **Wave Rating (0-10)** combines:
    - 🌊 Wave Height: Ideal range 1.2m - 3m
    - ⏱️ Wave Period: Best above 10s
    - 💨 Wind Speed: Optimal below 6 m/s
    - 🧭 Wind Direction: Offshore winds preferred
    - ⚡ Wave Energy: Higher energy for better rides
    
    **Travel Estimates:**
    - ⏰ Time: Based on distance and typical road conditions
    - 💰 Cost: Includes estimated fuel and tolls
    
    **Data Sources:**
    - Real-time surf forecasts
    - Local weather conditions
    - Historical spot data
    - Geographic features
    """)

st.markdown("---")

# Default map position (center of France)
base_position = [46.603354, 1.888334]

def setup_sidebar(day_list):
    """Set up the sidebar with input controls."""
    st.sidebar.title("🏄‍♂️ SurfMap")
    
    with st.sidebar.expander("🎯 Search Settings", expanded=True):
        # Address input
        address = st.text_input("🏠 Your location:", 
                              help="Enter your starting point (city, address, etc.)")
        validation_button = st.button("🔍 Find Surf Spots")
        
        # Forecast day selection
        selectbox_daily_forecast = st.selectbox(
            "📅 Select day:",
            day_list,
            help="Choose which day you want to surf"
        )
    
    # Rating filters
    with st.sidebar.expander("📊 Filters", expanded=True):
        option_forecast = st.slider(
            "Minimum wave rating (0-10):",
            min_value=0,
            max_value=10,
            value=0,
            help="Filter spots based on wave quality"
        )
        
        option_distance_h = st.slider(
            "Maximum travel time (hours):",
            min_value=0,
            max_value=24,
            value=24,
            help="Limit how far you're willing to travel"
        )
        
        option_prix = st.slider(
            "Maximum travel cost (€):",
            min_value=0,
            max_value=500,
            value=500,
            help="Set your budget limit for travel costs"
        )
    
    # Display options
    with st.sidebar.expander("🎨 Display Options", expanded=True):
        checkbox_choix_couleur = st.radio(
            "Color markers by:",
            ["🏄‍♂️ Wave Rating", "⏱️ Travel Time", "💸 Cost"],
            help="Choose how to color the markers on the map"
        )
    
    # Add tips in the sidebar
    with st.sidebar.expander("💡 Tips", expanded=False):
        st.markdown("""
        - Try different days to find the best conditions
        - Adjust filters to narrow down your options
        - Click markers for detailed spot information
        - Use the map controls to zoom and pan
        """)
    
    return (
        address,
        validation_button,
        option_forecast,
        option_prix,
        option_distance_h,
        selectbox_daily_forecast,
        checkbox_choix_couleur
    )

def color_by_rating(value: float, max_value: float, type: str = "rating") -> str:
    """Return color based on value relative to maximum."""
    if type == "rating":
        if value >= 7:
            return 'darkgreen'
        elif value >= 5:
            return 'green'
        elif value >= 3:
            return 'orange'
        elif value > 0:
            return 'red'
        return 'lightgray'
    else:  # For cost and time (inverse scale - lower is better)
        ratio = value / max_value
        if ratio <= 0.25:
            return 'darkgreen'
        elif ratio <= 0.5:
            return 'green'
        elif ratio <= 0.75:
            return 'orange'
        return 'red'

def create_popup_text(spot_info: dict, forecast: dict, selected_day: str) -> str:
    """Create popup text for a surf spot marker."""
    daily_rating = forecast.get(selected_day, 0.0)
    
    # Get rating color class
    rating_color = color_by_rating(daily_rating, 10, "rating")
    rating_class = {
        'darkgreen': 'excellent',
        'green': 'good',
        'orange': 'fair',
        'red': 'poor',
        'lightgray': 'no-data'
    }[rating_color]
    
    # CSS for styling
    style = """
    <style>
        .surf-popup h4 { margin-bottom: 5px; color: #2c3e50; }
        .surf-popup hr { margin: 10px 0; border-color: #eee; }
        .surf-popup .section { margin-bottom: 10px; }
        .surf-popup .label { color: #7f8c8d; font-size: 0.9em; }
        .surf-popup .value { color: #2c3e50; font-weight: bold; }
        .surf-popup .rating { font-size: 1.2em; padding: 2px 5px; border-radius: 3px; }
        .surf-popup .excellent { background: #27ae60; color: white; }
        .surf-popup .good { background: #2ecc71; color: white; }
        .surf-popup .fair { background: #f39c12; color: white; }
        .surf-popup .poor { background: #e74c3c; color: white; }
        .surf-popup .no-data { background: #95a5a6; color: white; }
    </style>
    """
    
    # Base info that's always shown
    popup_text = f"""
    {style}
    <div class="surf-popup">
        <h4>🌊 {spot_info['name']}</h4>
        <hr>
        
        <div class="section">
            <div class="label">📊 Today's Rating</div>
            <span class="rating {rating_class}">{daily_rating:.1f}/10</span>
        </div>
        
        <div class="section">
            <div class="label">📍 Location & Travel</div>
            <div>Distance: <span class="value">{spot_info['distance_km']:.1f} km</span></div>
            <div>Travel Time: <span class="value">{spot_info['distance_km'] / 60.0:.1f} hours</span></div>
            <div>Est. Cost: <span class="value">{spot_info['distance_km'] * 0.2:.2f} €</span></div>
        </div>
        
        <div class="section">
            <div class="label">🏄‍♂️ Spot Details</div>
            <div>Orientation: <span class="value">{spot_info['spot_orientation']}</span></div>
            <div>Avg Rating: <span class="value">{spot_info['average_rating']:.1f}/10</span></div>
        </div>
        
        <hr>
        <div style="font-size: 0.8em; color: #7f8c8d; text-align: center;">
            Click map for more options
        </div>
    </div>
    """
    
    return popup_text

def add_spot_markers(m: folium.Map, forecasts: dict, selected_day: str, 
                    color_by: str, max_time: float = 24.0, max_cost: float = 500.0,
                    min_rating: float = 0.0) -> None:
    """Add markers for all surf spots to the map."""
    marker_cluster = MarkerCluster().add_to(m)
    
    for spot_name, data in forecasts.items():
        spot_info = data['info']
        daily_forecasts = data['forecasts']
        daily_rating = daily_forecasts.get(selected_day, 0.0)
        
        # Apply filters
        if daily_rating < min_rating:
            continue
            
        travel_time = spot_info['distance_km'] / 60.0  # Rough estimate
        if travel_time > max_time:
            continue
            
        travel_cost = spot_info['distance_km'] * 0.2  # Rough estimate
        if travel_cost > max_cost:
            continue
        
        # Determine marker color
        if color_by == "🏄‍♂️ Wave Rating":
            color = color_by_rating(daily_rating, 10, "rating")
        elif color_by == "⏱️ Travel Time":
            color = color_by_rating(travel_time, max_time, "time")
        else:  # "💸 Cost"
            color = color_by_rating(travel_cost, max_cost, "cost")
        
        # Create and add marker
        popup_text = create_popup_text(spot_info, daily_forecasts, selected_day)
        
        # Get spot coordinates directly from info dictionary
        spot_lat = spot_info.get('latitude', 0.0)
        spot_lon = spot_info.get('longitude', 0.0)
        
        folium.Marker(
            location=[spot_lat, spot_lon],
            popup=folium.Popup(popup_text, max_width=220),
            icon=folium.Icon(color=color, icon='info-sign')
        ).add_to(marker_cluster)

def main():
    """Main application function."""
    # Get forecast days
    day_list = forecast_config.get_dayList_forecast()
    
    # Set up sidebar and get user inputs
    (address, validation_button, option_forecast, option_prix, 
     option_distance_h, selectbox_daily_forecast, checkbox_choix_couleur) = setup_sidebar(day_list)
    
    # Initialize map with default position
    m = folium.Map(location=base_position, zoom_start=6)
    
    # Add map controls
    MiniMap(toggle_display=True).add_to(m)
    Draw().add_to(m)
    
    # Process data if address is provided
    if address and validation_button:
        try:
            # Get forecasts for nearby spots
            forecasts = forecast_config.load_forecast_data(address, day_list)
            
            if forecasts:
                # Get coordinates of the search location
                lat, lon = forecast_config.get_coordinates(address)
                if lat is not None and lon is not None:
                    # Update map center
                    m = folium.Map(location=[lat, lon], zoom_start=8)
                    
                    # Add home marker
                    folium.Marker(
                        location=[lat, lon],
                        popup=folium.Popup("🏠 Home", max_width=150),
                        icon=folium.Icon(color='blue', icon='home')
                    ).add_to(m)
                    
                    # Re-add map controls
                    MiniMap(toggle_display=True).add_to(m)
                    Draw().add_to(m)
                    
                    # Add spot markers
                    add_spot_markers(
                        m, forecasts, selectbox_daily_forecast,
                        checkbox_choix_couleur, option_distance_h,
                        option_prix, option_forecast
                    )
                    
                    # Show success message
                    st.success(f"Found {len(forecasts)} surf spots near {address}")
                else:
                    st.error("Could not find the specified location")
            else:
                st.warning("No surf spots found in the area")
                
        except Exception as e:
            st.error(f"Error processing data: {str(e)}")
    
    # Display the map
    st.components.v1.html(m._repr_html_(), height=800)
    
    # Add footer
    st.markdown("---")
    st.markdown("Made with ❤️ by surf enthusiasts")

if __name__ == "__main__":
    main()
