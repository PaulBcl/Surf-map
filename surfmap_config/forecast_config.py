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
    Uses GPT-4 to generate realistic surf spot data.
    Returns a dictionary with detailed forecast data for the next 7 days.
    """
    try:
        today = datetime.now()
        prompt = f"""You are a surf forecasting expert. Given these coordinates: latitude {latitude}, longitude {longitude}, you MUST return EXACTLY 10 surf spots based on the following process:

### Step 1: Find Surf Spots
- Identify EXACTLY 10 surf spots within a 500 km radius from the given coordinates
- Use known surf spot databases (Surfline, MagicSeaweed, Windy, WindFinder)
- Include exact coordinates for each spot
- All spots must be real, plausible surf locations (beaches, reef breaks, etc.)
- Coordinates must be realistic for the region
- Distances must make geographical sense

### Step 2: Retrieve 7-Day Forecast from Multiple Sources
For each of the 10 spots, retrieve the following data and compute averages:
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

### Step 4: Return All 10 Spots
- Include ALL 10 spots in your response, sorted by rating
- Wave and wind conditions must be realistic for the region and season
- Each spot must have complete forecast data

Format your response as a JSON object following this structure (DO NOT copy these example values - generate realistic ones for each location):
{{
  "location": {{
    "latitude": {latitude},  # Use the provided search coordinates
    "longitude": {longitude}  # Use the provided search coordinates
  }},
  "best_spots": [
    {{
      "name": "<actual spot name>",  # Use real spot names for the region
      "latitude": "<spot latitude>",  # Use real coordinates
      "longitude": "<spot longitude>",  # Use real coordinates
      "distance_km": "<actual distance>",  # Calculate real distance from search point
      "average_rating": "<1-10 rating>",  # Based on conditions
      "spot_orientation": "<N/S/E/W/NW/etc>",  # Real orientation of the beach/break
      "forecast": [
        {{
          "date": "{today.strftime('%Y-%m-%d')}",  # Today's date
          "wave_height_m": {{  # Use realistic wave heights for the region/season
            "min": "<min height>",
            "max": "<max height>",
            "average": "<avg height>"
          }},
          "wave_period_s": "<realistic period>",  # Typical wave periods for the region
          "wave_energy_kj_m2": "<calculated energy>",  # Based on wave height and period
          "wind_speed_m_s": "<realistic speed>",  # Use typical wind speeds
          "wind_direction": "<actual direction>",  # Based on local weather patterns
          "daily_rating": "<1-10 rating>"  # Calculate based on all conditions
        }}
      ]
    }},
    # Repeat for all 10 spots with DIFFERENT, REALISTIC values for each
  ]
}}

IMPORTANT NOTES:
- DO NOT copy the example values shown above
- Generate unique, realistic values for each spot based on its actual location
- Ensure wave heights, periods, and wind conditions match typical patterns for the region
- Calculate distances accurately using the coordinates
- Use real spot names and locations from surf databases
- Provide different values for each spot - no duplicates

CRITICAL: You MUST return EXACTLY 10 spots in the best_spots array. No more, no less."""

        # Make the API call with adjusted parameters
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """You are a surf forecasting expert with extensive knowledge of surf spots worldwide.
You provide accurate, realistic surf spot data based on:
- Actual coastline geography
- Typical seasonal conditions
- Local weather patterns
- Known surf spot locations
- Wave mechanics and meteorology
Your responses must be precise, consistent, and always include exactly 10 spots."""},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.2,  # Lower temperature for more consistent responses
            presence_penalty=0.0,
            frequency_penalty=0.0
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

        # Verify we have exactly 10 spots
        if len(forecast_data.get('best_spots', [])) != 10:
            logger.error(f"GPT returned {len(forecast_data.get('best_spots', []))} spots instead of 10")
            # If we don't have 10 spots, try one more time with a stronger prompt
            return get_surf_forecast(latitude, longitude)

        return forecast_data

    except Exception as e:
        logger.error(f"Error getting surf forecasts: {str(e)}")
        return {
            "location": {
                "latitude": latitude,
                "longitude": longitude
            },
            "best_spots": []
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
