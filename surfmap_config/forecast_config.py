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

def get_surf_forecast(latitude: float, longitude: float) -> Dict:
    """
    Get comprehensive surf forecast data for the 10 best surf spots near the given coordinates.
    Uses multiple data sources and sophisticated rating criteria.
    Returns a dictionary with detailed forecast data for the next 10 days.
    """
    try:
        today = datetime.now()
        prompt = f"""### Task:
Given these coordinates: latitude {latitude}, longitude {longitude}, return the 10 best surf spots in the area based on surf conditions.

### Step 1: Find Surf Spots
- Identify all surf spots within a 500 km radius from the given coordinates.
- Use known surf spot databases (Surfline, MagicSeaweed, Windy, WindFinder).
- Include exact coordinates for each spot.

### Step 2: Retrieve 7-Day Forecast from Multiple Sources
For each surf spot, retrieve the following data and compute averages:
1. Wave Height (meters) - Minimum, maximum, and average wave height per day
2. Wave Period (seconds) - Time between wave peaks (longer = better)
3. Wave Energy (kJ/m²) - Strength of waves (higher energy = better rides)
4. Wind Speed (m/s) - Lower wind speeds are preferable
5. Wind Direction - Offshore winds improve wave shape, onshore winds deteriorate it

### Step 3: Rate Each Spot (0-10 Scale)
Compute a surfability score using these criteria:
- Wave Height: Ideal range = 1.2m - 3m
- Wave Period: Above 10s is good; below 7s is weak
- Wind Speed: Below 6 m/s is ideal
- Wind Direction: Offshore winds get a higher score
- Wave Energy: Higher energy is better for powerful waves

### Step 4: Select the 10 Best Spots
- Rank spots based on their average rating over the next 7 days
- Select the top 10 spots with the highest ratings

Return the data in this exact format:
{{
  "location": {{
    "latitude": {latitude},
    "longitude": {longitude}
  }},
  "best_spots": [
    {{
      "name": "Spot Name",
      "latitude": 46.123,  # Exact spot latitude
      "longitude": 1.456,  # Exact spot longitude
      "distance_km": 20.5,
      "average_rating": 8.5,
      "spot_orientation": "W",  # The direction the spot faces
      "forecast": [
        {{
          "date": "{today.strftime('%Y-%m-%d')}",  # Use this exact date format
          "wave_height_m": {{ "min": 1.5, "max": 3.2, "average": 2.4 }},
          "wave_period_s": 14,
          "wave_energy_kj_m2": 1500,
          "wind_speed_m_s": 4.5,
          "wind_direction": "NW",
          "daily_rating": 8
        }}
      ]
    }}
  ]
}}"""

        # Make the API call
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """You are a surf forecasting expert with access to multiple forecast sources and surf spot databases. 
You understand wave mechanics, meteorology, and how different factors affect surf conditions. 
You provide accurate forecasts based on real surf spot locations and typical conditions, considering:
- Seasonal patterns
- Local weather conditions
- Spot characteristics
- Historical data
- Geographic features"""},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.3  # Lower temperature for more consistent and factual responses
        )

        # Extract and parse the response
        forecast_str = response.choices[0].message.content.strip()
        start_idx = forecast_str.find('{')
        end_idx = forecast_str.rfind('}') + 1
        json_str = forecast_str[start_idx:end_idx]
        
        try:
            forecast_data = json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback to ast.literal_eval if JSON parsing fails
            forecast_data = ast.literal_eval(json_str)

        return forecast_data

    except Exception as e:
        logger.error(f"Error getting surf forecasts: {str(e)}")
        # Return default values if API call fails
        today = datetime.now()
        return {
            "location": {
                "latitude": latitude,
                "longitude": longitude
            },
            "best_spots": []  # Return empty list if no spots found
        }

@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_forecast_data(address: str, day_list: List[str]) -> Dict[str, Dict]:
    """
    Load forecast data for the 10 best surf spots near the given address.
    
    Args:
        address: Address to find nearby surf spots for
        day_list: List of days to get forecasts for
        
    Returns:
        Dictionary mapping spot names to their forecast data and ratings
    """
    try:
        # Get coordinates for the address
        latitude, longitude = get_coordinates(address)
        if latitude is None or longitude is None:
            raise ValueError(f"Could not geocode address: {address}")
            
        # Get forecasts for the best spots
        forecast_data = get_surf_forecast(latitude, longitude)
        if not forecast_data.get('best_spots'):
            raise ValueError("No surf spots found nearby")
            
        forecasts = {}
        
        # Process each spot's forecast
        for spot in forecast_data['best_spots']:
            try:
                logger.info(f"Processing forecast for spot: {spot['name']} at ({spot['latitude']}, {spot['longitude']})")
                # Create a mapping of ratings to days
                spot_forecasts = {}
                
                # Extract ratings from the forecast data
                for forecast in spot['forecast']:
                    date = datetime.strptime(forecast['date'], '%Y-%m-%d')
                    day_str = date.strftime('%A %d')
                    if day_str in day_list:
                        spot_forecasts[day_str] = float(forecast['daily_rating'])
                
                # Fill in any missing days with 0.0
                for day in day_list:
                    if day not in spot_forecasts:
                        spot_forecasts[day] = 0.0
                        
                # Store both forecasts and spot info
                forecasts[spot['name']] = {
                    'forecasts': spot_forecasts,
                    'info': {
                        'name': spot['name'],
                        'distance_km': spot['distance_km'],
                        'average_rating': spot['average_rating'],
                        'spot_orientation': spot['spot_orientation'],
                        'latitude': spot['latitude'],
                        'longitude': spot['longitude']
                    }
                }
                
            except Exception as e:
                logger.error(f"Failed to process forecast for {spot['name']}: {str(e)}")
                continue
                
        return forecasts
            
    except Exception as e:
        logger.error(f"Failed to load forecast data: {str(e)}")
        return {}

def get_dayList_forecast() -> List[str]:
    """
    Get list of forecast days in the correct format.
    Returns a list of the next 7 days in the format 'Day DD' (e.g., 'Monday 15').
    """
    try:
        days = []
        today = datetime.now()
        for i in range(7):
            day = today + timedelta(days=i)
            # Format day name and ensure day number is zero-padded
            days.append(day.strftime('%A %d'))  # %A for full day name, %d for zero-padded day
        return days
    except Exception as e:
        logger.error(f"Error generating forecast days: {str(e)}")
        # Return default days if there's an error
        return ['Monday 01', 'Tuesday 02', 'Wednesday 03', 'Thursday 04', 
                'Friday 05', 'Saturday 06', 'Sunday 07']
