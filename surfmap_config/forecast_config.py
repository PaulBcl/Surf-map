#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import logging
import openai
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import ast
from . import api_config

# OpenAI API Key (Make sure to store it securely in Streamlit secrets)
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_coordinates(address: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Convert an address to coordinates using Google Maps Geocoding API.
    Returns a tuple of (latitude, longitude) or (None, None) if geocoding fails.
    """
    try:
        result = api_config.get_google_results(address, api_config.gmaps_api_key)
        if result['success']:
            return result['latitude'], result['longitude']
        else:
            logger.error(f"Geocoding failed for address {address}: {result.get('error_message', 'Unknown error')}")
            return None, None
    except Exception as e:
        logger.error(f"Error geocoding address {address}: {str(e)}")
        return None, None

def get_surf_forecast(spot):
    """
    Get surf forecast data for the next 7 days.
    Uses GPT to simulate getting real forecast data for the spot's location.
    """
    try:
        today = datetime.now()
        
        # First, get the raw forecast data
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a surf forecasting API that provides accurate weather and wave data.
You return raw forecast data without any interpretation, similar to what would come from services like Surfline or Windy.
Provide realistic values based on:
- The location's typical seasonal patterns
- Local weather systems
- Ocean and coastal dynamics"""},
                {"role": "user", "content": f"""Get the 7-day forecast for coordinates: {spot['latitude']}, {spot['longitude']}
Location: {spot['name']}, {spot['region']}

Return raw forecast data for the next 7 days starting from {today.strftime('%Y-%m-%d')}.

Format as JSON:
{{
  "forecast": [
    {{
      "date": "YYYY-MM-DD",
      "wave_height_m": {{ "min": float, "max": float, "average": float }},
      "wave_period_s": float,
      "wave_energy_kj_m2": float,
      "wind_speed_m_s": float,
      "wind_direction": "direction",
      "tide_state": "low/rising/high/falling"
    }}
  ]
}}

IMPORTANT:
- Provide realistic values for this location and season
- Consider typical local wind patterns
- Account for seasonal swell patterns
- Include accurate tide cycles"""}
            ],
            max_tokens=1000,
            temperature=0.7
        )

        # Parse the raw forecast
        forecast_str = response.choices[0].message.content.strip()
        start_idx = forecast_str.find('{')
        end_idx = forecast_str.rfind('}') + 1
        json_str = forecast_str[start_idx:end_idx]
        
        try:
            forecast_data = json.loads(json_str)
        except json.JSONDecodeError:
            forecast_data = ast.literal_eval(json_str)

        # Now analyze how well these conditions match the spot's characteristics
        analyzed_forecasts = analyze_spot_conditions(spot, forecast_data['forecast'])
        
        return analyzed_forecasts

    except Exception as e:
        logger.error(f"Error getting surf forecast for {spot['name']}: {str(e)}")
        return []

def analyze_spot_conditions(spot, raw_forecasts):
    """
    Analyze how well the forecasted conditions match the spot's characteristics.
    Uses GPT to compare forecast data with spot's known behavior.
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a surf spot analysis expert.
You analyze how well forecasted conditions match a spot's known characteristics.
Consider all aspects of the spot's behavior to rate the conditions."""},
                {"role": "user", "content": f"""Analyze these forecasted conditions for {spot['name']}:
{json.dumps(raw_forecasts, indent=2)}

Based on the spot's characteristics:
Type: {spot['type']}
Orientation: {spot['orientation']}
Best Season: {spot['best_season']}
Ideal Swell: {spot['swell_compatibility']['ideal_swell_size_m']}m from {spot['swell_compatibility']['ideal_swell_direction']}
Best Wind: {spot['wind_compatibility']['best_direction']}
Tide Behavior: {spot['tide_behavior']}

For each day's forecast, add a 'daily_rating' (0-10) and 'conditions_analysis' explaining:
1. How well the wind direction and speed match the spot's preferences
2. Whether wave height and period are in the ideal range
3. How the tide state affects the spot
4. Overall suitability for surfing

Return the enhanced forecast data with your analysis added to each day."""}
            ],
            max_tokens=1500,
            temperature=0.7
        )

        # Parse the analysis
        analysis_str = response.choices[0].message.content.strip()
        start_idx = analysis_str.find('[')
        end_idx = analysis_str.rfind(']') + 1
        
        try:
            analyzed_forecasts = json.loads(analysis_str[start_idx:end_idx])
        except json.JSONDecodeError:
            analyzed_forecasts = ast.literal_eval(analysis_str[start_idx:end_idx])

        return analyzed_forecasts

    except Exception as e:
        logger.error(f"Error analyzing conditions for {spot['name']}: {str(e)}")
        return raw_forecasts  # Return raw forecasts if analysis fails

def calculate_spot_rating(spot, forecast_conditions):
    """
    Calculate a spot's rating based on how well current conditions match its ideal characteristics.
    """
    try:
        # Get spot's ideal conditions
        ideal_wind = spot['wind_compatibility']['best_direction']
        ideal_swell = spot['swell_compatibility']
        tide_behavior = spot['tide_behavior']
        
        # Calculate wind rating
        wind_rating = spot['wind_compatibility']['quality']
        if forecast_conditions['wind_direction'] not in ideal_wind:
            wind_rating *= 0.5  # Reduce rating if wind direction is not ideal
        
        # Calculate swell rating
        swell_rating = spot['swell_compatibility']['quality']
        current_swell = forecast_conditions['wave_height_m']['average']
        ideal_swell_range = spot['swell_compatibility']['ideal_swell_size_m']
        if not (ideal_swell_range[0] <= current_swell <= ideal_swell_range[1]):
            swell_rating *= 0.5  # Reduce rating if swell size is outside ideal range
        
        # Calculate tide rating (using rising tide as default if no tide info in forecast)
        tide_rating = spot['tide_behavior']['rising']['quality']
        
        # Calculate overall rating
        overall_rating = (
            wind_rating * 0.3 +
            swell_rating * 0.4 +
            tide_rating * 0.3
        )
        
        return round(overall_rating, 1)
        
    except Exception as e:
        logger.error(f"Error calculating rating for {spot['name']}: {str(e)}")
        return 0.0

def load_lisbon_spots():
    """
    Load the Lisbon area surf spots from the JSON file.
    """
    try:
        with open('lisbon_area.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data['spots']
    except Exception as e:
        logger.error(f"Error loading Lisbon spots: {str(e)}")
        return []

def get_spot_forecast(spot):
    """
    Generate a forecast for a spot.
    This can be enhanced later with real API data.
    """
    ideal_swell = spot['swell_compatibility']['ideal_swell_size_m']
    return {
        'wave_height_m': {
            'min': ideal_swell[0],
            'max': ideal_swell[1],
            'average': sum(ideal_swell) / 2
        },
        'wave_period_s': '12',  # Default value, can be updated with real data
        'wind_speed_m_s': '5',  # Default value, can be updated with real data
        'wind_direction': spot['wind_compatibility']['best_direction'],
        'daily_rating': calculate_spot_rating(spot, spot)
    }

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_forecast_data(address: str = None, day_list: list = None, coordinates: list = None) -> list:
    """
    Load forecast data for surf spots in the Lisbon area.
    """
    try:
        # Load Lisbon spots
        spots = load_lisbon_spots()
        if not spots:
            raise ValueError("No spots found in Lisbon area data")
            
        # Process each spot
        for spot in spots:
            # Get forecast data using GPT
            forecasts = get_surf_forecast(spot)
            
            # Calculate ratings based on forecasted conditions
            for forecast in forecasts:
                forecast['daily_rating'] = calculate_spot_rating(spot, forecast)
            
            spot['forecast'] = forecasts
            
            # Calculate distance if coordinates provided
            if coordinates:
                from math import radians, sin, cos, sqrt, atan2
                
                def haversine_distance(lat1, lon1, lat2, lon2):
                    R = 6371  # Earth's radius in kilometers
                    
                    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
                    dlat = lat2 - lat1
                    dlon = lon2 - lon1
                    
                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                    c = 2 * atan2(sqrt(a), sqrt(1-a))
                    distance = R * c
                    
                    return round(distance, 1)
                
                spot['distance_km'] = haversine_distance(
                    coordinates[0], coordinates[1],
                    float(spot['latitude']), float(spot['longitude'])
                )
            else:
                spot['distance_km'] = 0
                
        # Sort spots by distance if coordinates provided
        if coordinates:
            spots.sort(key=lambda x: x['distance_km'])
            
        return spots
        
    except Exception as e:
        logger.error(f"Error loading forecast data: {str(e)}")
        return []

def get_dayList_forecast():
    """Get list of forecast days."""
    today = datetime.now()
    days = []
    for i in range(7):
        day = today + timedelta(days=i)
        days.append(day.strftime('%A %d').replace('0', ' ').lstrip())
    return days
