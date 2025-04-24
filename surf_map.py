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
    page_title="🌴 SurfMap",
    page_icon="🏄‍♂️",
    layout="wide"
)

# Create a session state for the reset functionality
if 'run_id' not in st.session_state:
    st.session_state.run_id = 0

def get_user_location():
    """Get user's current location using Streamlit's geolocation."""
    try:
        # Get location from Streamlit's geolocation
        location = st.session_state.get('location')
        if location and 'latitude' in location and 'longitude' in location:
            return [location['latitude'], location['longitude']]
        return None
    except Exception as e:
        st.warning(f"Could not get location: {str(e)}")
        return None

def create_responsive_layout(day_list):
    """Create a responsive layout for the application."""
    # Create containers for different sections
    header_container = st.container()
    filters_container = st.container()
    map_container = st.container()
    suggestions_container = st.container()
    footer_container = st.container()
    
    # Welcome block - full width
    st.markdown("""
    <div style='text-align: center; margin-bottom: 1.5rem;'>
        <h1 style='margin-bottom: 0.5rem; font-size: 1.8rem;'>Bienvenue dans l'application 🌊 Surfmap !</h1>
        <p style='margin-bottom: 0.5rem; font-size: 1rem; color: #666;'>Trouvez le spot de surf parfait près de chez vous</p>
        <div style='display: inline-block; padding: 0.5rem 1rem; background-color: #e6ffe6; border-radius: 0.5rem; font-size: 0.9rem; margin-bottom: 1rem;'>
            New release🌴! Les conditions de surf sont désormais disponibles
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Create two equal-height columns for the controls
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Date selection
        with st.expander("📅 Choisir la journée pour vos prévisions", expanded=True):
            label_daily_forecast = "Jour souhaité pour l'affichage des prévisions de surf"
            selectbox_daily_forecast = st.selectbox(label_daily_forecast, day_list)
            
            # Legend integrated within date selection
            st.markdown("---")
            st.markdown("##### 🗺️ Légende de la carte")
            st.markdown(":triangular_flag_on_post: représente un spot de surf")
            st.markdown("La couleur donne la qualité du spot à partir de vos critères :")
            st.markdown("- :green_book: Parfait pour surfer")
            st.markdown("- :orange_book: Conditions moyennes")
            st.markdown("- :closed_book: Déconseillé")
    
    with col2:
        # Guide d'utilisation with improved content
        with st.expander("ℹ️ Guide d'utilisation", expanded=True):
            st.markdown("##### Comment utiliser Surfmap")
            st.markdown("""
            1. 📍 La carte s'affiche automatiquement centrée sur votre position (🏠)
            2. 📅 Sélectionnez le jour souhaité pour voir les prévisions
            3. 🎯 Les spots sont affichés par couleur selon leur qualité :
               - 🟢 Vert : conditions idéales
               - 🟡 Orange : conditions acceptables
               - 🔴 Rouge : conditions déconseillées
            4. ℹ️ Cliquez sur un spot pour voir ses détails
            """)
    
    # Return default values for removed UI elements
    address = None
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
    if user_location:
        # Use user's location as the base position
        base_position = user_location
        st.session_state.forecasts = forecast_config.load_forecast_data(None, day_list, user_location)
    else:
        # Fallback to default position
        base_position = [46.603354, 1.888334]  # Center of France
        st.warning("Could not get your location. Using default position.")
    
    # Initialize map with user's position
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
                m, st.session_state.forecasts, selectbox_daily_forecast,
                checkbox_choix_couleur, option_distance_h,
                option_prix, option_forecast
            )
            
            st.success(f"Found {len(st.session_state.forecasts)} surf spots near your location")
        except Exception as e:
            st.error(f"Error processing data: {str(e)}")
    
    # Display the map in the map container
    with st.container():
        st.components.v1.html(m._repr_html_(), height=600)
    
    # Add suggestions section
    create_suggestions_section()
    
    # Add footer
    st.markdown("---")
    st.markdown("Made with ❤️ by surf enthusiasts")

if __name__ == "__main__":
    main()
