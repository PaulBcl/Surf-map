#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import logging
import openai
from openai import OpenAI
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import ast
from . import api_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing OpenAI client: {str(e)}")
    client = None

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
    Get surf forecast data for the next 7 days using ChatGPT.
    Returns None if no valid forecast can be generated.
    """
    try:
        if not client:
            logger.error("OpenAI client not initialized")
            return None
            
        today = datetime.now()
        days = []
        forecasts = []
        
        # Generate next 7 days
        for i in range(7):
            day = today + timedelta(days=i)
            days.append(day)
        
        # Get GPT-generated forecast
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a surf forecasting expert with knowledge of global surf conditions.
You provide accurate, realistic surf forecasts based on:
- Location and regional patterns
- Seasonal conditions
- Local weather systems
- Ocean and coastal dynamics"""},
                {"role": "user", "content": f"""Generate a 7-day forecast for:
Location: {spot.get('name', 'Unknown')}, {spot.get('region', 'Unknown')}
Coordinates: {spot.get('latitude', 0)}, {spot.get('longitude', 0)}
Type: {spot.get('type', 'Unknown')}
Orientation: {spot.get('orientation', 'Unknown')}
Best Season: {spot.get('best_season', 'Unknown')}

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
      "tide_state": "low/rising/high/falling",
      "daily_rating": float
    }}
  ]
}}

IMPORTANT:
- Provide realistic values based on current conditions and weather patterns
- Consider seasonal patterns and local geography
- All numeric values must be realistic and in metric units
- Wind directions must be cardinal points (N, NE, E, SE, etc.)
- Tide states must be one of: low/rising/high/falling
- Daily rating must be between 0 and 10"""}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        # Parse the GPT forecast
        forecast_str = response.choices[0].message.content.strip()
        start_idx = forecast_str.find('{')
        end_idx = forecast_str.rfind('}') + 1
        if start_idx == -1 or end_idx <= start_idx:
            logger.error(f"Invalid forecast format for {spot.get('name', 'Unknown')}")
            return None
            
        try:
            forecast_data = json.loads(forecast_str[start_idx:end_idx])
            if not isinstance(forecast_data, dict) or 'forecast' not in forecast_data:
                logger.error(f"Missing forecast data for {spot.get('name', 'Unknown')}")
                return None
            
            # Validate and process each day's forecast
            for day_forecast in forecast_data['forecast']:
                if not all(key in day_forecast for key in ['date', 'wave_height_m', 'wave_period_s', 'wind_speed_m_s', 'wind_direction', 'tide_state', 'daily_rating']):
                    logger.error(f"Missing required fields in forecast for {spot.get('name', 'Unknown')}")
                    return None
                
                # Ensure wave height has all required fields
                wave_height = day_forecast['wave_height_m']
                if not all(key in wave_height for key in ['min', 'max', 'average']):
                    logger.error(f"Invalid wave height format for {spot.get('name', 'Unknown')}")
                    return None
            
            return forecast_data['forecast']
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing forecast JSON for {spot.get('name', 'Unknown')}: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting forecast for {spot.get('name', 'Unknown')}: {str(e)}")
        return None

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
        response = client.chat.completions.create(
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
        import os
        # Get the directory containing this script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to the project root
        project_root = os.path.dirname(current_dir)
        # Construct the path to the JSON file
        json_path = os.path.join(project_root, 'lisbon_area.json')
        
        logger.info(f"Loading spots from: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            spots = data.get('spots', [])
            if not spots:
                logger.error("No spots found in JSON data")
                return []
            logger.info(f"Successfully loaded {len(spots)} spots")
            return spots
    except Exception as e:
        logger.error(f"Error loading Lisbon spots: {str(e)}")
        return []

def get_spot_forecast(spot):
    """
    Generate a forecast for a spot.
    Returns a forecast in the standard format.
    """
    try:
        today = datetime.now()
        ideal_swell = spot['swell_compatibility']['ideal_swell_size_m']
        
        return {
            'date': today.strftime('%Y-%m-%d'),
            'wave_height_m': {
                'min': float(ideal_swell[0]),
                'max': float(ideal_swell[1]),
                'average': sum(ideal_swell) / 2
            },
            'wave_period_s': 12.0,
            'wave_energy_kj_m2': 25.0,
            'wind_speed_m_s': 5.0,
            'wind_direction': spot['wind_compatibility']['best_direction'],
            'tide_state': 'rising',
            'daily_rating': calculate_spot_rating(spot, {
                'wave_height_m': {
                    'min': float(ideal_swell[0]),
                    'max': float(ideal_swell[1]),
                    'average': sum(ideal_swell) / 2
                },
                'wave_period_s': 12.0,
                'wind_speed_m_s': 5.0,
                'wind_direction': spot['wind_compatibility']['best_direction'],
                'tide_state': 'rising'
            })
        }
    except Exception as e:
        logger.error(f"Error generating spot forecast for {spot.get('name', 'unknown')}: {str(e)}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_forecast_data(address: str = None, day_list: list = None, coordinates: list = None) -> list:
    """
    Load forecast data for surf spots in the Lisbon area.
    Only returns spots that have valid forecast data.
    """
    try:
        logger.info("Starting to load forecast data")
        logger.info(f"Input - Address: {address}, Coordinates: {coordinates}")
        
        # Load Lisbon spots
        spots = load_lisbon_spots()
        if not spots:
            logger.error("No spots found in Lisbon area data")
            return []
        
        logger.info(f"Loaded {len(spots)} spots from Lisbon area data")
        
        # Process each spot
        processed_spots = []
        for spot in spots:
            try:
                logger.info(f"Processing spot: {spot.get('name', 'Unknown')}")
                
                # Get forecast data using GPT
                forecast = get_surf_forecast(spot)
                if not forecast:
                    logger.warning(f"No valid forecast data for {spot.get('name', 'Unknown')}, skipping")
                    continue
                
                logger.info(f"Got valid forecast for {spot.get('name', 'Unknown')}")
                
                # Add forecast to spot data
                spot_with_forecast = spot.copy()
                spot_with_forecast['forecast'] = forecast
                
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
                    
                    try:
                        distance = haversine_distance(
                            coordinates[0], coordinates[1],
                            float(spot['latitude']), float(spot['longitude'])
                        )
                        logger.info(f"Distance to {spot.get('name', 'Unknown')}: {distance} km")
                        spot_with_forecast['distance_km'] = distance
                    except Exception as e:
                        logger.error(f"Error calculating distance for {spot.get('name', 'Unknown')}: {str(e)}")
                        continue
                
                processed_spots.append(spot_with_forecast)
                
            except Exception as e:
                logger.error(f"Error processing spot: {str(e)}")
                continue
        
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
