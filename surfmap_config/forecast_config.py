#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import logging
import openai
from openai import OpenAI, AsyncOpenAI
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union
import ast
import os
import time
import asyncio
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI clients
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    async_client = AsyncOpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    logger.info("OpenAI clients initialized successfully")
except Exception as e:
    logger.error(f"Error initializing OpenAI clients: {str(e)}")
    client = None
    async_client = None

# Create a semaphore to limit concurrent API calls
MAX_CONCURRENT_CALLS = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT_CALLS)

async def get_surf_forecast_async(spot):
    """
    Async version of get_surf_forecast that gets surf forecast data for the next 7 days using ChatGPT.
    Returns None if no valid forecast can be generated.
    """
    try:
        if not async_client:
            logger.error("Async OpenAI client not initialized")
            return None
            
        today = datetime.now()
        days = []
        forecasts = []
        
        # Generate next 7 days
        for i in range(7):
            day = today + timedelta(days=i)
            days.append(day)
        
        # Use semaphore to limit concurrent API calls
        async with semaphore:
            # Get GPT-generated forecast
            response = await async_client.chat.completions.create(
                model="gpt-4",
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

@st.cache_data(ttl=21600, show_spinner=False)  # Cache for 6 hours, hide spinner
def get_cached_gpt_response(spot_name: str, spot_data: str, forecast_date: str) -> dict:
    """
    Cached wrapper for GPT API calls.
    Returns the raw GPT response for caching.
    """
    try:
        if not client:
            logger.error("OpenAI client not initialized")
            return None
            
        spot = json.loads(spot_data)
        response = client.chat.completions.create(
            model="gpt-4",
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
        return {'response': response.choices[0].message.content.strip()}
    except Exception as e:
        logger.error(f"Error getting GPT response for {spot_name}: {str(e)}")
        return None

def process_gpt_response(response_text: str, spot_name: str) -> list:
    """Process the GPT response text into forecast data."""
    try:
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        if start_idx == -1 or end_idx <= start_idx:
            logger.error(f"Invalid forecast format for {spot_name}")
            return None
            
        forecast_data = json.loads(response_text[start_idx:end_idx])
        if not isinstance(forecast_data, dict) or 'forecast' not in forecast_data:
            logger.error(f"Missing forecast data for {spot_name}")
            return None
        
        # Validate forecast data
        for day_forecast in forecast_data['forecast']:
            if not all(key in day_forecast for key in ['date', 'wave_height_m', 'wave_period_s', 'wind_speed_m_s', 'wind_direction', 'tide_state', 'daily_rating']):
                logger.error(f"Missing required fields in forecast for {spot_name}")
                return None
            
            wave_height = day_forecast['wave_height_m']
            if not all(key in wave_height for key in ['min', 'max', 'average']):
                logger.error(f"Invalid wave height format for {spot_name}")
                return None
        
        return forecast_data['forecast']
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing forecast JSON for {spot_name}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error processing forecast for {spot_name}: {str(e)}")
        return None

def get_surf_forecast(spot):
    """
    Get surf forecast data for a spot using cached GPT responses.
    """
    try:
        spot_data = json.dumps(spot)
        cached_response = get_cached_gpt_response(
            spot_name=spot['name'],
            spot_data=spot_data,
            forecast_date=datetime.now().strftime('%Y-%m-%d')
        )
        
        if not cached_response:
            return None
            
        return process_gpt_response(cached_response['response'], spot['name'])
    except Exception as e:
        logger.error(f"Error in forecast for {spot.get('name', 'Unknown')}: {str(e)}")
        return None

def get_forecasts_batch(spots):
    """
    Process multiple spots using cached responses.
    Returns a list of forecasts in the same order as the input spots.
    """
    forecasts = []
    for spot in spots:
        try:
            forecast = get_surf_forecast(spot)
            forecasts.append(forecast)
        except Exception as e:
            logger.error(f"Error getting forecast for {spot.get('name', 'Unknown')}: {str(e)}")
            forecasts.append(None)
    return forecasts

def get_coordinates(address: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Convert an address to coordinates using Google Maps Geocoding API.
    Returns a tuple of (latitude, longitude) or (None, None) if geocoding fails.
    """
    try:
        from . import api_config  # Import here to avoid circular imports
        result = api_config.get_google_results(address, api_config.gmaps_api_key)
        if result.get('success'):
            return result.get('latitude'), result.get('longitude')
        else:
            logger.error(f"Geocoding failed for address {address}: {result.get('error_message', 'Unknown error')}")
            return None, None
    except Exception as e:
        logger.error(f"Error geocoding address {address}: {str(e)}")
        return None, None

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

@st.cache_data(ttl=21600, show_spinner=False)  # Cache for 6 hours, hide spinner
def get_conditions_analysis(spot, forecast):
    """
    Generate a detailed analysis of how well the forecasted conditions match the spot's characteristics.
    Cached for 6 hours based on spot name and forecast date.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a surf spot analysis expert who provides clear, concise assessments of surf conditions."},
                {"role": "user", "content": f"""Analyze these forecasted conditions for {spot['name']} on {forecast['date']}:
{json.dumps(forecast, indent=2)}

Based on the spot's characteristics:
Type: {spot['type']}
Orientation: {spot['orientation']}
Best Season: {spot['best_season']}
Difficulty: {', '.join(spot['difficulty'])}
Wave Description: {spot.get('wave_description', 'No description available')}

Swell Compatibility:
- Ideal Size: {spot['swell_compatibility']['ideal_swell_size_m']}m
- Best Direction: {spot['swell_compatibility']['ideal_swell_direction']}
- Quality Rating: {spot['swell_compatibility']['quality']}/5
- Notes: {spot['swell_compatibility'].get('notes', '')}

Wind Compatibility:
- Best Direction: {spot['wind_compatibility']['best_direction']}
- Quality Rating: {spot['wind_compatibility']['quality']}/5
- Notes: {spot['wind_compatibility'].get('notes', '')}

Tide Behavior:
Low: {spot['tide_behavior']['low'].get('note', '')} (Quality: {spot['tide_behavior']['low']['quality']}/5)
Rising: {spot['tide_behavior']['rising'].get('note', '')} (Quality: {spot['tide_behavior']['rising']['quality']}/5)
High: {spot['tide_behavior']['high'].get('note', '')} (Quality: {spot['tide_behavior']['high']['quality']}/5)
Falling: {spot['tide_behavior']['falling'].get('note', '')} (Quality: {spot['tide_behavior']['falling']['quality']}/5)

Local Tips: {spot.get('local_tips', '')}

Explain:
1. How well wind direction and speed match the spot's preferences.
2. Whether wave height and period are in the ideal range.
3. Tide behavior impact.
4. Suitability for surfing (considering difficulty level).
5. Brief mention of any hazards or local considerations.

Use concise, user-friendly language."""}
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

def load_lisbon_spots(file_obj=None):
    """
    Load surf spots from the Lisbon area JSON file.
    Args:
        file_obj: Optional file-like object from st.file_uploader
    """
    try:
        # Check if data is already in session state
        if 'surf_spots_data' in st.session_state and st.session_state.surf_spots_data is not None:
            logger.info("Loading spots from session state")
            return st.session_state.surf_spots_data

        if file_obj is not None:
            # Handle file uploader object
            logger.info("Loading spots from uploaded file")
            try:
                file_content = file_obj.getvalue().decode('utf-8')
            except UnicodeDecodeError:
                logger.error("File encoding error - trying with different encodings")
                try:
                    file_content = file_obj.getvalue().decode('latin-1')
                except:
                    logger.error("Failed to decode file content")
                    return []
        else:
            # Load from default data file
            try:
                # Use streamlit's working directory
                json_path = os.path.join("data", "lisbon_area_lean.json")
                logger.info(f"Looking for JSON file at: {json_path}")
                
                # Ensure data directory exists
                os.makedirs("data", exist_ok=True)
                
                if not os.path.exists(json_path):
                    logger.error(f"JSON file not found at: {json_path}")
                    return []
                
                logger.info(f"Loading spots from: {json_path}")
                with open(json_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            except Exception as e:
                logger.error(f"Error reading file: {str(e)}")
                return []

        logger.info(f"File content length: {len(file_content)} bytes")
        try:
            data = json.loads(file_content)
            logger.info(f"JSON structure keys: {list(data.keys())}")
            spots = data.get('spots', [])
            logger.info(f"Number of spots found: {len(spots)}")
            
            if not spots:
                logger.error("No spots found in JSON data")
                return []
            
            # Store in session state
            st.session_state.surf_spots_data = spots
            logger.info(f"Successfully loaded {len(spots)} spots")
            return spots
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            error_context = file_content[max(0, e.pos-50):min(len(file_content), e.pos+50)]
            logger.error(f"Error context: ...{error_context}...")
            return []

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

@st.cache_data(ttl=21600, show_spinner=False)  # Cache for 6 hours, hide spinner
def get_quick_summary(spot, forecast):
    """
    Generate a quick 1-2 sentence summary of why this spot is recommended today.
    Cached for 6 hours based on spot name and forecast date.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a surf expert helping travelers quickly understand why a spot is good today. Provide a 1-2 sentence summary based on the following data."},
                {"role": "user", "content": f"""Spot: {spot['name']} ({spot['region']})
Current conditions for {forecast['date']}:
- Waves: {forecast['wave_height_m']['min']}-{forecast['wave_height_m']['max']}m
- Wind: {forecast['wind_direction']} @ {forecast['wind_speed_m_s']} m/s
- Tide: {forecast['tide_state']}

Spot characteristics:
- Type: {spot['type']}
- Best season: {spot['best_season']}
- Difficulty: {', '.join(spot['difficulty'])}
- Ideal swell: {spot['swell_compatibility']['ideal_swell_size_m']}m from {spot['swell_compatibility']['ideal_swell_direction']}
- Best wind: {spot['wind_compatibility']['best_direction']}
- Best tide: {spot['tide_behavior']['low']['note'] if spot['tide_behavior']['low']['quality'] >= 4 else spot['tide_behavior']['rising']['note']}

Explain in 1-2 sentences why this spot is a good pick today based on these conditions."""}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Error generating quick summary for {spot['name']}: {str(e)}")
        return "Summary not available."

@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour, hide spinner
def load_forecast_data(address: str = None, day_list: list = None, coordinates: list = None, file_obj = None) -> list:
    """
    Load forecast data for surf spots in the Lisbon area.
    Only returns spots that have valid forecast data.
    Args:
        address: Optional address string
        day_list: Optional list of days in YYYY-MM-DD format
        coordinates: Optional [lat, lon] coordinates
        file_obj: Optional file-like object from st.file_uploader
    Returns:
        list: List of processed spots with forecasts
    """
    try:
        logger.info("Starting to load forecast data")
        logger.info(f"Input - Address: {address}, Day list: {day_list}, Coordinates: {coordinates}")
        
        # Initialize progress tracking
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        status_text.text("Loading surf spots data...")
        
        # Load Lisbon spots
        spots = load_lisbon_spots(file_obj)
        if not spots:
            logger.error("No spots found in Lisbon area data")
            status_text.text("No surf spots found in the area")
            return []
        
        logger.info(f"Loaded {len(spots)} spots from Lisbon area data")
        total_spots = len(spots)
        
        # Get the selected date from the day_list
        selected_date = datetime.now()  # fallback
        if day_list and len(day_list) > 0:
            try:
                selected_date = datetime.strptime(day_list[0], '%Y-%m-%d')
                logger.info(f"Using selected date: {selected_date}")
            except (ValueError, IndexError) as e:
                logger.warning(f"Could not parse date from day_list, using today: {e}")
        
        # Process spots in batches
        processed_spots = []
        try:
            # Get forecasts for all spots concurrently
            status_text.text("Fetching forecasts for all spots...")
            forecasts = asyncio.run(get_forecasts_batch(spots))
            
            # Process the results
            for i, (spot, forecast) in enumerate(zip(spots, forecasts)):
                try:
                    # Update progress
                    current_progress = (i + 1) / total_spots
                    progress_bar.progress(current_progress)
                    status_text.text(f"Analyzing {spot.get('name', 'Unknown')} ({i+1}/{total_spots})")
                    
                    if not forecast:
                        logger.warning(f"No valid forecast data for {spot.get('name', 'Unknown')}, skipping")
                        continue
                    
                    # Update the forecast date to match selected date
                    if forecast and len(forecast) > 0:
                        forecast[0]['date'] = selected_date.strftime('%Y-%m-%d')
                    
                    logger.info(f"Got valid forecast for {spot.get('name', 'Unknown')}")
                    
                    # Generate conditions analysis and quick summary for top spots
                    try:
                        conditions_analysis = get_conditions_analysis(spot, forecast[0])
                        if conditions_analysis:
                            forecast[0]['conditions_analysis'] = conditions_analysis
                        
                        # Generate quick summary (will be used for top 3 spots)
                        quick_summary = get_quick_summary(spot, forecast[0])
                        if quick_summary:
                            forecast[0]['quick_summary'] = quick_summary
                            
                        logger.info(f"Generated analysis and summary for {spot.get('name', 'Unknown')}")
                    except Exception as e:
                        logger.error(f"Error generating analysis for {spot.get('name', 'Unknown')}: {str(e)}")
                        forecast[0]['conditions_analysis'] = "Unable to generate analysis."
                        forecast[0]['quick_summary'] = "Summary not available."
                    
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
            
        except Exception as e:
            logger.error(f"Error in batch processing: {str(e)}")
        
        # Final status update
        if processed_spots:
            status_text.text(f"Successfully analyzed {len(processed_spots)} surf spots")
            progress_bar.progress(1.0)
        else:
            status_text.text("No suitable surf spots found")
        
        # Keep the progress bar visible for a moment so users can see completion
        time.sleep(1)
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
                
        logger.info(f"Successfully processed {len(processed_spots)} spots")
        return processed_spots
            
    except Exception as e:
        logger.error(f"Error loading forecast data: {str(e)}")
        if 'status_text' in locals():
            status_text.text(f"Error: {str(e)}")
        if 'progress_bar' in locals():
            progress_bar.empty()
        return []

def get_dayList_forecast():
    """Get list of forecast days."""
    today = datetime.now()
    days = []
    for i in range(7):
        day = today + timedelta(days=i)
        days.append(day.strftime('%A %d').replace('0', ' ').lstrip())
    return days
