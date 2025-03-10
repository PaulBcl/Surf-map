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
    Uses GPT-3.5-turbo to generate realistic surf spot data.
    Returns a dictionary with detailed forecast data for the next 7 days.
    """
    try:
        today = datetime.now()
        
        # Make the API call with adjusted parameters
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": """You are a surf forecasting expert with extensive knowledge of surf spots worldwide.
You provide accurate, realistic surf spot data based on:
- Actual coastline geography
- Typical seasonal conditions
- Local weather patterns
- Known surf spot locations
- Wave mechanics and meteorology

CRITICAL REQUIREMENTS:
1. ONLY return spots that are within 500 km of the given coordinates
2. If no spots are found within 500 km, return an empty list
3. Return up to 10 spots, but ONLY if they are within range
4. All spots must be real, plausible surf locations (beaches, reef breaks, etc.)
5. Coordinates must be realistic for the region
6. Wave and wind conditions must be realistic for the region and season
7. Generate unique values for each spot - no duplicates
8. Sort spots by proximity to the search coordinates

Rating System (0-10 Scale):
- Wave Height (0-10): Ideal range 1.2m - 3m
  * 0: No waves or dangerous conditions
  * 5: Acceptable conditions (0.5-1m or 3-4m)
  * 10: Perfect conditions (1.2-3m)
- Wave Period:
  * 0-3: Below 7s (weak waves)
  * 4-7: 7-10s (moderate)
  * 8-10: Above 10s (strong, clean waves)
- Wind Speed:
  * 0-3: Strong winds (>12 m/s)
  * 4-7: Moderate winds (6-12 m/s)
  * 8-10: Light winds (<6 m/s)
- Wind Direction:
  * 0-3: Strong onshore
  * 4-7: Cross-shore
  * 8-10: Offshore
- Overall Rating: Weighted average of above factors"""},
                {"role": "user", "content": f"""Given these coordinates: latitude {latitude}, longitude {longitude}, find surf spots following this process:

### Step 1: Find Surf Spots
- Calculate the distance to known surf spots near the coordinates
- ONLY include spots within 500 km of the given coordinates
- If no spots are found within 500 km, return an empty list
- Return up to 10 spots, sorted by proximity
- Use known surf spot databases (Surfline, MagicSeaweed, Windy, WindFinder)
- Include exact coordinates for each spot
- All spots must be real, plausible surf locations (beaches, reef breaks, etc.)
- Coordinates must be realistic for the region
- Sort by proximity to the given coordinates

### Step 2: Retrieve 7-Day Forecast from Multiple Sources
For each spot within range, retrieve the following data and compute averages:
1. Wave Height (meters) - Minimum, maximum, and average wave height per day
2. Wave Period (seconds) - Time between wave peaks (longer = better)
3. Wave Energy (kJ/m²) - Strength of waves (higher energy = better rides)
4. Wind Speed (m/s) - Lower wind speeds are preferable
5. Wind Direction - Offshore winds improve wave shape, onshore winds deteriorate it

### Step 3: Rate Each Spot
- Calculate ratings based on the rating system defined above
- Ensure ratings reflect actual surfing conditions
- Consider seasonal patterns and local characteristics
- Account for regional wave and weather patterns

Format as JSON:
{{
  "location": {{ "latitude": {latitude}, "longitude": {longitude} }},
  "best_spots": [
    {{
      "name": "<real spot name>",
      "latitude": "<actual lat>",
      "longitude": "<actual lon>",
      "distance_km": "<calculated distance>",
      "average_rating": "<0-10 rating>",
      "spot_orientation": "<N/S/E/W/NW/etc>",
      "forecast": [
        {{
          "date": "{today.strftime('%Y-%m-%d')}
          "wave_height_m": {{ "min": "<min>", "max": "<max>", "average": "<avg>" }},
          "wave_period_s": "<period>",
          "wave_energy_kj_m2": "<energy>",
          "wind_speed_m_s": "<speed>",
          "wind_direction": "<dir>",
          "daily_rating": "<0-10 rating>"
        }}
      ]
    }}
  ]
}}

IMPORTANT:
- DO NOT copy example values - generate real, accurate data
- Ensure all coordinates and distances are geographically accurate
- Ratings MUST reflect actual surfing conditions using the rating system
- ONLY return spots within 500 km of the given coordinates
- If no spots are within 500 km, return an empty list
- Sort spots by proximity to search location"""}
            ],
            max_tokens=2000,
            temperature=0.1,  # Reduced temperature for more consistent results
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

        # Verify all spots are within range
        spots = forecast_data.get('best_spots', [])
        valid_spots = [spot for spot in spots if float(spot['distance_km']) <= 500]
        
        if len(valid_spots) != len(spots):
            logger.error(f"Removing {len(spots) - len(valid_spots)} spots that were beyond 500 km")
            forecast_data['best_spots'] = valid_spots

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
