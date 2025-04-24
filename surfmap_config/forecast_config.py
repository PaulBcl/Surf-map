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
    Get surf forecast data for the next 7 days by combining:
    1. Real forecast data from surf websites
    2. GPT-generated forecast based on location and conditions
    """
    try:
        # Get forecasts from all available sources
        all_forecasts = []
        
        # 1. Get forecasts from provided websites
        for forecast_link in spot['surf_forecast_link']:
            try:
                response = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": """You are a surf forecasting expert who can analyze forecast data from surf websites.
You extract and interpret forecast data from websites like Surf-Forecast, MagicSeaweed, and Surfline.
You return the data in a standardized format."""},
                        {"role": "user", "content": f"""Extract the 7-day forecast data from this link: {forecast_link}
for the spot: {spot['name']}, {spot['region']}

Return the raw forecast data in this format:
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
- Extract actual forecast data from the website
- Convert all measurements to metric units
- Standardize wind directions to cardinal points (N, NE, E, SE, etc.)
- Standardize tide states to low/rising/high/falling"""}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                
                # Parse the website forecast
                forecast_str = response.choices[0].message.content.strip()
                start_idx = forecast_str.find('{')
                end_idx = forecast_str.rfind('}') + 1
                json_str = forecast_str[start_idx:end_idx]
                
                try:
                    website_forecast = json.loads(json_str)
                    all_forecasts.append(website_forecast['forecast'])
                except (json.JSONDecodeError, KeyError):
                    logger.warning(f"Could not parse forecast from {forecast_link}")
                    continue
                    
            except Exception as e:
                logger.warning(f"Error getting forecast from {forecast_link}: {str(e)}")
                continue
        
        # 2. Get GPT-generated forecast
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a surf forecasting expert with knowledge of global surf conditions.
You provide accurate, realistic surf forecasts based on:
- Location and regional patterns
- Seasonal conditions
- Local weather systems
- Ocean and coastal dynamics"""},
                {"role": "user", "content": f"""Generate a 7-day forecast for:
Location: {spot['name']}, {spot['region']}
Coordinates: {spot['latitude']}, {spot['longitude']}

Return forecast data in this format:
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
        
        # Parse the GPT forecast
        forecast_str = response.choices[0].message.content.strip()
        start_idx = forecast_str.find('{')
        end_idx = forecast_str.rfind('}') + 1
        json_str = forecast_str[start_idx:end_idx]
        
        try:
            gpt_forecast = json.loads(json_str)
            all_forecasts.append(gpt_forecast['forecast'])
        except (json.JSONDecodeError, KeyError):
            logger.warning("Could not parse GPT-generated forecast")
        
        # 3. Merge and analyze all forecasts
        if not all_forecasts:
            raise ValueError("No valid forecasts available")
            
        # Get the final analyzed forecast
        analyzed_forecast = analyze_spot_conditions(spot, all_forecasts)
        return analyzed_forecast

    except Exception as e:
        logger.error(f"Error getting surf forecast for {spot['name']}: {str(e)}")
        return []

def analyze_spot_conditions(spot, all_forecasts):
    """
    Analyze and merge multiple forecast sources to create a reliable forecast.
    """
    try:
        # Get the number of days to forecast
        num_days = len(all_forecasts[0])
        
        # Initialize merged forecast
        merged_forecast = []
        
        # For each day, merge data from all sources
        for day_idx in range(num_days):
            day_data = {
                'date': all_forecasts[0][day_idx]['date'],
                'wave_height_m': {'min': [], 'max': [], 'average': []},
                'wave_period_s': [],
                'wave_energy_kj_m2': [],
                'wind_speed_m_s': [],
                'wind_direction': [],
                'tide_state': []
            }
            
            # Collect data from all sources
            for forecast in all_forecasts:
                if day_idx < len(forecast):
                    day = forecast[day_idx]
                    day_data['wave_height_m']['min'].append(day['wave_height_m']['min'])
                    day_data['wave_height_m']['max'].append(day['wave_height_m']['max'])
                    day_data['wave_height_m']['average'].append(day['wave_height_m']['average'])
                    day_data['wave_period_s'].append(day['wave_period_s'])
                    day_data['wave_energy_kj_m2'].append(day['wave_energy_kj_m2'])
                    day_data['wind_speed_m_s'].append(day['wind_speed_m_s'])
                    day_data['wind_direction'].append(day['wind_direction'])
                    day_data['tide_state'].append(day['tide_state'])
            
            # Calculate averages and most common values
            merged_day = {
                'date': day_data['date'],
                'wave_height_m': {
                    'min': round(sum(day_data['wave_height_m']['min']) / len(day_data['wave_height_m']['min']), 1),
                    'max': round(sum(day_data['wave_height_m']['max']) / len(day_data['wave_height_m']['max']), 1),
                    'average': round(sum(day_data['wave_height_m']['average']) / len(day_data['wave_height_m']['average']), 1)
                },
                'wave_period_s': round(sum(day_data['wave_period_s']) / len(day_data['wave_period_s']), 1),
                'wave_energy_kj_m2': round(sum(day_data['wave_energy_kj_m2']) / len(day_data['wave_energy_kj_m2']), 1),
                'wind_speed_m_s': round(sum(day_data['wind_speed_m_s']) / len(day_data['wind_speed_m_s']), 1),
                'wind_direction': max(set(day_data['wind_direction']), key=day_data['wind_direction'].count),
                'tide_state': max(set(day_data['tide_state']), key=day_data['tide_state'].count)
            }
            
            # Calculate rating and analysis
            merged_day['daily_rating'] = calculate_spot_rating(spot, merged_day)
            merged_day['conditions_analysis'] = get_conditions_analysis(spot, merged_day)
            
            merged_forecast.append(merged_day)
        
        return merged_forecast

    except Exception as e:
        logger.error(f"Error analyzing spot conditions for {spot['name']}: {str(e)}")
        return []

def get_conditions_analysis(spot, forecast):
    """
    Generate a detailed analysis of how well the forecasted conditions match the spot's characteristics.
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a surf spot analysis expert.
You analyze how well forecasted conditions match a spot's known characteristics.
Consider all aspects of the spot's behavior to rate the conditions."""},
                {"role": "user", "content": f"""Analyze these forecasted conditions for {spot['name']}:
{json.dumps(forecast, indent=2)}

Based on the spot's characteristics:
Type: {spot['type']}
Orientation: {spot['orientation']}
Best Season: {spot['best_season']}
Ideal Swell: {spot['swell_compatibility']['ideal_swell_size_m']}m from {spot['swell_compatibility']['ideal_swell_direction']}
Best Wind: {spot['wind_compatibility']['best_direction']}
Tide Behavior: {spot['tide_behavior']}

Provide a detailed analysis explaining:
1. How well the wind direction and speed match the spot's preferences
2. Whether wave height and period are in the ideal range
3. How the tide state affects the spot
4. Overall suitability for surfing
5. Any potential hazards or special considerations

Return a concise but informative analysis."""}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Error generating conditions analysis for {spot['name']}: {str(e)}")
        return "Unable to generate detailed analysis."

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
        logger.info("Starting to load forecast data")
        logger.info(f"Input - Address: {address}, Coordinates: {coordinates}")
        
        # Load Lisbon spots
        spots = load_lisbon_spots()
        if not spots:
            logger.error("No spots found in Lisbon area data")
            raise ValueError("No spots found in Lisbon area data")
        
        logger.info(f"Loaded {len(spots)} spots from Lisbon area data")
        
        # Process each spot
        processed_spots = []
        for spot in spots:
            try:
                logger.info(f"Processing spot: {spot['name']}")
                
                # Get forecast data using GPT
                forecasts = get_surf_forecast(spot)
                logger.info(f"Got {len(forecasts)} days of forecast for {spot['name']}")
                
                # Add forecasts to spot data
                spot_with_forecast = spot.copy()
                spot_with_forecast['forecast'] = forecasts
                
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
                    
                    distance = haversine_distance(
                        coordinates[0], coordinates[1],
                        float(spot['latitude']), float(spot['longitude'])
                    )
                    logger.info(f"Distance to {spot['name']}: {distance} km")
                    spot_with_forecast['distance_km'] = distance
                else:
                    spot_with_forecast['distance_km'] = 0
                
                processed_spots.append(spot_with_forecast)
                
            except Exception as e:
                logger.error(f"Error processing spot {spot['name']}: {str(e)}")
                continue
        
        # Sort spots by distance if coordinates provided
        if coordinates and processed_spots:
            processed_spots.sort(key=lambda x: x['distance_km'])
            logger.info("Sorted spots by distance")
        
        logger.info(f"Successfully processed {len(processed_spots)} spots")
        return processed_spots
        
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
