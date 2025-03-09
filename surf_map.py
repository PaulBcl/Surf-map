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

def setup_sidebar(dayList):
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
            st.session_state.run_id += 1

        # Forecast day selection
        label_daily_forecast = "Jour souhaité pour l'affichage des prévisions de surf"
        selectbox_daily_forecast = st.selectbox(label_daily_forecast, dayList)

        # Sliders
        option_forecast = st.slider("Conditions minimum souhaitées (/10)", min_value=0, max_value=10,
                                  key=f"forecast_{st.session_state.run_id}", help="En définissant les prévisions à 0, tous les résultats s'affichent")
        option_prix = st.slider("Prix maximum souhaité (€, pour un aller)", min_value=0, max_value=200,
                              key=f"prix_{st.session_state.run_id}", help="En définissant le prix à 0€, tous les résultats s'affichent")
        option_distance_h = st.slider("Temps de conduite souhaité (heures)", min_value=0, max_value=15,
                                    key=f"distance_{st.session_state.run_id}", help="En définissant le temps maximal de conduite à 0h, tous les résultats s'affichent")

        # Country selection
        label_choix_pays = "Choix des pays pour les spots à afficher"
        list_pays = ["🇫🇷 France", "🇪🇸 Espagne", "🇮🇹 Italie"]
        multiselect_pays = st.multiselect(label_choix_pays, list_pays, default=list_pays[0], key=f"pays_{st.session_state.run_id}")

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

# Default map position (center of France)
base_position = [46.603354, 1.888334]

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
            <div>Travel Time: <span class="value">{spot_info['distance_km']:.1f} hours</span></div>
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
    
    st.write(f"Adding markers for {len(forecasts)} surf spots...")
    added_markers = 0
    
    for spot_name, data in forecasts.items():
        spot_info = data['info']
        daily_forecasts = data['forecasts']
        daily_rating = daily_forecasts.get(selected_day, 0.0)
        
        # Apply filters
        if daily_rating < min_rating:
            st.write(f"Skipping {spot_name} due to low rating: {daily_rating}")
            continue
            
        # Calculate travel time in hours (assuming average speed of 80 km/h)
        travel_time = spot_info['distance_km'] / 80.0
        if travel_time > max_time:
            st.write(f"Skipping {spot_name} due to long travel time: {travel_time:.1f} hours")
            continue
            
        travel_cost = spot_info['distance_km'] * 0.2  # Rough estimate
        if travel_cost > max_cost:
            st.write(f"Skipping {spot_name} due to high cost: {travel_cost:.2f} €")
            continue
        
        # Determine marker color
        if color_by == "🌊 Wave Rating":
            color = color_by_rating(daily_rating, 10, "rating")
        elif color_by == "⏱️ Travel Time":
            color = color_by_rating(travel_time, max_time, "time")
        else:  # "💰 Cost"
            color = color_by_rating(travel_cost, max_cost, "cost")
        
        # Create and add marker
        popup_text = create_popup_text(spot_info, daily_forecasts, selected_day)
        
        # Get spot coordinates directly from info dictionary
        spot_lat = spot_info.get('latitude')
        spot_lon = spot_info.get('longitude')
        
        if spot_lat is None or spot_lon is None:
            st.write(f"Skipping {spot_name} due to missing coordinates")
            continue
            
        try:
            marker = folium.Marker(
                location=[spot_lat, spot_lon],
                popup=folium.Popup(popup_text, max_width=220),
                icon=folium.Icon(color=color, icon='info-sign')
            )
            marker.add_to(marker_cluster)
            added_markers += 1
            st.write(f"Added marker for {spot_name} at ({spot_lat}, {spot_lon})")
        except Exception as e:
            st.write(f"Error adding marker for {spot_name}: {str(e)}")
    
    st.write(f"Successfully added {added_markers} markers to the map")

def main():
    """Main application function."""
    # Get forecast days
    day_list = forecast_config.get_dayList_forecast()
    
    # Set up sidebar and get user inputs
    (address, validation_button, option_forecast, option_prix, 
     option_distance_h, selectbox_daily_forecast, multiselect_pays, checkbox_choix_couleur) = setup_sidebar(day_list)
    
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
