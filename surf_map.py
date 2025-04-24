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
    elif type == "time":  # For travel time (lower is better)
        if max_value == 0:  # Using relative scale
            if value <= 2:  # Under 2 hours
                return 'darkgreen'
            elif value <= 4:  # 2-4 hours
                return 'green'
            elif value <= 6:  # 4-6 hours
                return 'orange'
            else:  # Over 6 hours
                return 'red'
        else:  # Using max_value scale
            ratio = value / max_value
            if ratio <= 0.25:
                return 'darkgreen'
            elif ratio <= 0.5:
                return 'green'
            elif ratio <= 0.75:
                return 'orange'
            return 'red'
    else:  # For cost (lower is better)
        if max_value == 0:  # Using relative scale
            if value <= 20:  # Under 20€
                return 'darkgreen'
            elif value <= 50:  # 20-50€
                return 'green'
            elif value <= 80:  # 50-80€
                return 'orange'
            else:  # Over 80€
                return 'red'
        else:  # Using max_value scale
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
            <div>Travel Time: <span class="value">{spot_info['distance_km'] / 80.0:.1f} hours</span></div>
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
        
    # Create an expander for logging messages
    with st.expander("Détails du chargement des spots", expanded=False):
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
            # Only apply travel time filter if max_time is greater than 0
            if max_time > 0 and travel_time > max_time:
                st.write(f"Skipping {spot_name} due to long travel time: {travel_time:.1f} hours")
                continue
                
            # Calculate travel cost (0.2€ per km)
            travel_cost = spot_info['distance_km'] * 0.2  # Rough estimate
            # Only apply cost filter if max_cost is greater than 0
            if max_cost > 0 and travel_cost > max_cost:
                st.write(f"Skipping {spot_name} due to high cost: {travel_cost:.2f} €")
                continue
            
            # Determine marker color
            if color_by == "🌊 Wave Rating":
                color = color_by_rating(daily_rating, 10, "rating")
            elif color_by == "⏱️ Travel Time":
                if max_time > 0:
                    color = color_by_rating(travel_time, max_time, "time")
                else:
                    # When max_time is 0, use a relative scale based on all spots
                    color = color_by_rating(travel_time, 10, "time")  # Using 10 hours as reference
            else:  # "💰 Cost"
                if max_cost > 0:
                    color = color_by_rating(travel_cost, max_cost, "cost")
                else:
                    # When max_cost is 0, use a relative scale based on typical costs
                    color = color_by_rating(travel_cost, 100, "cost")  # Using 100€ as reference
            
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

def create_responsive_layout(day_list):
    """Create a responsive layout for the application."""
    # Create containers for different sections
    header_container = st.container()
    filters_container = st.container()
    map_container = st.container()
    suggestions_container = st.container()
    footer_container = st.container()
    
    with header_container:
        # Welcome message and instructions
        st.markdown("Bienvenue dans l'application :ocean: Surfmap !")
        st.markdown("Cette application a pour but de vous aider à identifier le meilleur spot de surf accessible depuis votre ville ! Bon ride :surfer:")
        st.success("New release🌴! Les conditions de surf sont désormais disponibles pour optimiser votre recherche !")
        
        # Guide d'utilisation
        explication_expander = st.expander("Guide d'utilisation")
        with explication_expander:
            st.write("Vous pourrez trouver ci-dessous une carte affichant les principaux spots de surf accessibles depuis votre ville. Pour cela, il suffit d'indiquer votre position et appuyer sur 'Soumettre l'adresse'.")
            st.write("La carte qui s'affiche ci-dessous indique votre position (🏠 en bleu) ainsi que les différents spots en proposant les meilleurs spots (en vert 📗, modifiable ci-dessous dans 'code couleur') et en affichant les informations du spot lorsque vous cliquez dessus.")
            st.write("Vous pouvez affiner les spots proposés en sélectionnant les options avancées et en filtrant sur vos prérequis. Ces choix peuvent porter sur (i) le prix (💸) maximum par aller, (ii) le temps de parcours (⏳) acceptable, (iii) le pays de recherche (🇫🇷) et (iv) les conditions prévues (🏄) des spots recherchés !")
    
    with filters_container:
        # Create a card-like container for filters
        with st.container():
            st.markdown("### 🔍 Filtres de recherche")
            
            # Create columns for filters - responsive layout
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # Address input
                address = st.text_input("Renseignez votre ville", value='', max_chars=None, key=None, type='default', help=None)
                
                # Forecast day selection
                label_daily_forecast = "Jour souhaité pour l'affichage des prévisions de surf"
                selectbox_daily_forecast = st.selectbox(label_daily_forecast, day_list)
            
            with col2:
                # Country selection
                label_choix_pays = "Choix des pays pour les spots à afficher"
                list_pays = ["🇫🇷 France", "🇪🇸 Espagne", "🇮🇹 Italie"]
                multiselect_pays = st.multiselect(label_choix_pays, list_pays, default=list_pays[0], key=f"pays_{st.session_state.run_id}")
            
            # Submit button
            validation_button = st.button("Soumettre l'adresse", key=None, help=None)
    
    # Legend in a collapsible section
    with st.expander("Légende de la carte", expanded=False):
        st.markdown(":triangular_flag_on_post: représente un spot de surf")
        st.markdown("La couleur donne la qualité du spot à partir de vos critères : :green_book: parfait, :orange_book: moyen, :closed_book: déconseillé")
    
    # Return default values for removed UI elements
    option_forecast = 0
    option_prix = 0
    option_distance_h = 0
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
    
    # Initialize map with default position
    m = folium.Map(location=base_position, zoom_start=6)
    
    # Add map controls
    MiniMap(toggle_display=True).add_to(m)
    Draw().add_to(m)
    
    # Process data if address is provided or forecasts exist in session state
    if validation_button:
        try:
            # Get forecasts for nearby spots
            st.session_state.forecasts = forecast_config.load_forecast_data(address, day_list)
        except Exception as e:
            st.error(f"Error processing data: {str(e)}")
            st.session_state.forecasts = None
    
    # If we have forecasts (either from this run or stored in session), display them
    if st.session_state.forecasts:
        try:
            # Get coordinates of the search location
            home_lat, home_lon = forecast_config.get_coordinates(address)
            if home_lat is not None and home_lon is not None:
                try:
                    # Calculate bounds including home and all surf spots
                    lats = [home_lat]
                    lons = [home_lon]
                    
                    # Collect all valid coordinates
                    valid_spots = 0
                    for spot_data in st.session_state.forecasts.values():
                        spot_info = spot_data['info']
                        spot_lat = spot_info.get('latitude')
                        spot_lon = spot_info.get('longitude')
                        if (spot_lat is not None and spot_lon is not None and 
                            isinstance(spot_lat, (int, float)) and isinstance(spot_lon, (int, float)) and
                            -90 <= spot_lat <= 90 and -180 <= spot_lon <= 180):
                            lats.append(spot_lat)
                            lons.append(spot_lon)
                            valid_spots += 1
                    
                    if valid_spots == 0:
                        # If no valid spots found, center on home with default zoom
                        m = folium.Map(location=[home_lat, home_lon], zoom_start=8)
                    else:
                        # Calculate center and bounds
                        center_lat = (max(lats) + min(lats)) / 2
                        center_lon = (max(lons) + min(lons)) / 2
                        
                        # Validate center coordinates
                        if not (-90 <= center_lat <= 90 and -180 <= center_lon <= 180):
                            # Fallback to home location if center is invalid
                            center_lat, center_lon = home_lat, home_lon
                        
                        # Create map centered on calculated position
                        m = folium.Map(location=[center_lat, center_lon])
                        
                        try:
                            # Calculate the maximum distance between points
                            lat_range = max(lats) - min(lats)
                            lon_range = max(lons) - min(lons)
                            
                            # If points are too close, use a minimum range
                            if lat_range < 0.1 and lon_range < 0.1:
                                # Add a small buffer for very close points
                                min_lats = min(lats) - 0.05
                                max_lats = max(lats) + 0.05
                                min_lons = min(lons) - 0.05
                                max_lons = max(lons) + 0.05
                            else:
                                min_lats = min(lats)
                                max_lats = max(lats)
                                min_lons = min(lons)
                                max_lons = max(lons)
                            
                            # Fit bounds with padding
                            m.fit_bounds([[min_lats, min_lons], [max_lats, max_lons]], padding=[50, 50])
                        except Exception as e:
                            st.warning(f"Could not optimize map view: {str(e)}. Using default zoom level.")
                            m = folium.Map(location=[center_lat, center_lon], zoom_start=8)
                    
                    # Add home marker
                    folium.Marker(
                        location=[home_lat, home_lon],
                        popup=folium.Popup("🏠 Home", max_width=150),
                        icon=folium.Icon(color='blue', icon='home')
                    ).add_to(m)
                    
                    # Re-add map controls
                    MiniMap(toggle_display=True).add_to(m)
                    Draw().add_to(m)
                    
                    # Add spot markers
                    add_spot_markers(
                        m, st.session_state.forecasts, selectbox_daily_forecast,
                        checkbox_choix_couleur, option_distance_h,
                        option_prix, option_forecast
                    )
                    
                    if validation_button:
                        st.success(f"Found {valid_spots} valid surf spots near {address}")
                except Exception as e:
                    st.warning(f"Error calculating map bounds: {str(e)}. Using default view.")
                    m = folium.Map(location=[home_lat, home_lon], zoom_start=8)
            else:
                st.error("Could not find the specified location")
        except Exception as e:
            st.error(f"Error processing data: {str(e)}")
    elif validation_button:
        st.warning("No surf spots found in the area")
    
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
