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
import re

def degrees_to_cardinal(degrees: float) -> str:
    try:
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        idx = round(((degrees % 360) / 45)) % 8
        return directions[idx]
    except Exception:
        return "Unknown"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STORMGLASS_API_KEY = st.secrets["stormglass_api"]

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
                model="gpt-4o",
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
            model="gpt-4o",
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
            
        # Clean the JSON string
        clean_text = response_text[start_idx:end_idx]
        clean_text = clean_text.replace("```json", "").replace("```", "")
        clean_text = re.sub(r",\s*}", "}", clean_text)
        clean_text = re.sub(r",\s*]", "]", clean_text)
            
        forecast_data = json.loads(clean_text)
        if not isinstance(forecast_data, dict) or 'forecast' not in forecast_data:
            logger.error(f"Missing forecast data for {spot_name}")
            return None
        
        # Validate forecast data
        for day_forecast in forecast_data['forecast']:
            if not all(key in day_forecast for key in ['date', 'wave_height_m', 'wave_period_s', 'wind_speed_m_s', 'wind_direction', 'tide_state', 'daily_rating']):
                logger.error(f"Missing required fields in forecast for {spot_name}")
                return None
            
            wave_height = day_forecast['wave_height_m']
            # Check if wave_height is a dictionary or a direct value
            if isinstance(wave_height, dict):
                if not all(key in wave_height for key in ['min', 'max', 'average']):
                    logger.error(f"Invalid wave height format for {spot_name}")
                    return None
            elif not isinstance(wave_height, (int, float)):
                logger.error(f"Invalid wave height type for {spot_name}")
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
            merged_day['conditions_analysis'] = get_conditions_analysis(spot, merged_day['date'])
            
            merged_forecast.append(merged_day)
        
        return merged_forecast

    except Exception as e:
        logger.error(f"Error analyzing spot conditions for {spot['name']}: {str(e)}")
        return []

@st.cache_data(ttl=21600, show_spinner=False)  # Cache for 6 hours, hide spinner
def get_conditions_analysis(spot: dict, date: str) -> str:
    """
    Generate an analysis for a specific spot on a specific date using:
    - Stormglass real forecast data
    - Static spot metadata
    Returns a GPT-generated analysis string.
    """
    try:
        logger.info(f"[get_conditions_analysis] Starting for spot: {spot.get('name')} on date: {date}")
        
        sg_forecasts = get_stormglass_forecast(spot)
        logger.info(f"[get_conditions_analysis] Stormglass forecasts received: {json.dumps(sg_forecasts, indent=2) if sg_forecasts else None}")
        
        if not sg_forecasts:
            logger.warning(f"[get_conditions_analysis] No Stormglass forecast available for {spot.get('name')}")
            return "Stormglass forecast unavailable. Cannot generate analysis."

        forecast_for_day = next((f for f in sg_forecasts if f["date"] == date), None)
        logger.info(f"[get_conditions_analysis] Forecast for day {date}: {json.dumps(forecast_for_day, indent=2) if forecast_for_day else None}")
        
        if not forecast_for_day:
            logger.warning(f"[get_conditions_analysis] No forecast found for date {date}")
            return "No forecast data available for this date. Please check back later or try a different day."

        context = f"""
You're a surf forecasting expert.

Your task is to assess how suitable the surf will be on {date} at {spot['name']} (Portugal), based on:
- Structural spot features
- Forecasted swell, wind, and tide conditions

Here is what you know about the spot:
- Type: {spot.get("type", "N/A")}
- Orientation: {spot.get("orientation", "N/A")}
- Best season: {spot.get("best_season", "N/A")}
- Ideal swell: {spot.get("swell_compatibility", {}).get("ideal_swell_direction", "N/A")} at {spot.get("swell_compatibility", {}).get("ideal_swell_size_m", "N/A")} m
- Ideal wind: {spot.get("wind_compatibility", {}).get("best_direction", "N/A")}
- Tide behavior (low): {spot.get("tide_behavior", {}).get("low", {}).get("note", "N/A")}
- Tide behavior (rising): {spot.get("tide_behavior", {}).get("rising", {}).get("note", "N/A")}
- Tide behavior (high): {spot.get("tide_behavior", {}).get("high", {}).get("note", "N/A")}
- Tide behavior (falling): {spot.get("tide_behavior", {}).get("falling", {}).get("note", "N/A")}
- Crowd: {spot.get("crowd_pressure", {}).get("notes", "N/A")}

Here's the forecasted data from Stormglass for this day:
- Swell height: {forecast_for_day['wave_height_m']} m
- Swell direction: {forecast_for_day.get('wave_direction_deg', 'N/A')}°
- Wind speed: {forecast_for_day['wind_speed_m_s']} m/s
- Wind direction: {degrees_to_cardinal(forecast_for_day['wind_direction_deg'])}
- Tide level: {forecast_for_day.get('tide_height_m', 'N/A')} m

In your answer, explain how the forecast matches (or doesn't match) the spot's ideal conditions. 
Give 1–2 surf tips if relevant (e.g., best tide, crowd notes, local insight).

Your answer should be surfer-friendly but based on real analysis.
"""
        logger.info(f"[get_conditions_analysis] GPT Context prepared for {spot.get('name')}")

        prompt = f"""Given the surf spot data and real forecast below, assess how good the conditions will be for surfers on {date}. Include local tips, potential issues, and whether it's worth going.
Context:
{context}

Return a short paragraph and end with a 1–5 quality score (e.g., "Overall: 4/5").
"""
        logger.info(f"[get_conditions_analysis] Sending prompt to GPT for {spot.get('name')}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )

        logger.info(f"[GPT Raw Output - {spot['name']} on {date}] {response.choices[0].message.content}")
        logger.info(f"[get_conditions_analysis] GPT Response received for {spot.get('name')}")

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"[get_conditions_analysis] GPT analysis failed for {spot.get('name')} on {date}: {e}")
        return "Error generating analysis."

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
        logger.info(f"[get_quick_summary] Starting for spot: {spot.get('name')} on date: {forecast.get('date')}")
        logger.info(f"[get_quick_summary] Input forecast data: {json.dumps(forecast, indent=2)}")

        # Safely handle wind direction conversion
        wind_deg = forecast.get('wind_direction_deg')
        wind_cardinal = degrees_to_cardinal(wind_deg) if isinstance(wind_deg, (float, int)) else "Unknown"
        logger.info(f"[get_quick_summary] Wind direction: {wind_deg} degrees -> {wind_cardinal}")

        context = f"""
You're a surf forecaster.

Give a **short and sharp** summary of the surf quality at {spot['name']} on {forecast['date']}, based on the forecast and spot compatibility.

Use the info below:
- Spot orientation: {spot.get("orientation", "N/A")}
- Ideal swell: {spot.get("swell_compatibility", {}).get("ideal_swell_direction", "N/A")} at {spot.get("swell_compatibility", {}).get("ideal_swell_size_m", "N/A")} m
- Ideal wind: {spot.get("wind_compatibility", {}).get("best_direction", "N/A")}
- Forecasted swell: {forecast['wave_height_m']} m from {forecast.get('wave_direction_deg', 'N/A')}°
- Forecasted wind: {forecast['wind_speed_m_s']} m/s from {wind_cardinal}

Keep it to 1-2 sentences max, and be direct about whether it's good or not.
"""
        logger.info(f"[get_quick_summary] GPT Context prepared: {context}")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": context}],
            temperature=0.5,
        )

        logger.info(f"[GPT Raw Output - {spot['name']} on {forecast['date']}] {response.choices[0].message.content}")
        logger.info(f"[get_quick_summary] GPT Response received for {spot['name']}")

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"[get_quick_summary] Error generating quick summary for {spot.get('name')}: {str(e)}")
        return "Summary not available."

def load_forecast_data(address: str, day_list: list, coordinates: list) -> list:
    """
    Load forecast data for all spots in the specified area.
    Returns a list of spots with their forecasts.
    """
    try:
        logger.info("Starting to load forecast data")
        logger.info(f"Input - Address: {address}, Day list: {day_list}, Coordinates: {coordinates}")
        
        # Load spots from JSON file
        spots = load_lisbon_spots()
        if not spots:
            logger.error("No spots found to process")
            return []
            
        logger.info(f"Loaded {len(spots)} spots from {address} area data")
        
        # Get the selected date
        selected_date = day_list[0] if day_list and len(day_list) > 0 else datetime.now().strftime('%Y-%m-%d')
        logger.info(f"Using selected date: {selected_date}")
        
        # Process each spot
        spots_with_forecast = []
        for spot in spots:
            try:
                # Generate forecast for the spot
                forecast = generate_forecast_for_spot(spot, selected_date)
                
                # Create a copy of the spot with forecast
                spot_with_forecast = spot.copy()
                spot_with_forecast['forecast'] = forecast
                
                spots_with_forecast.append(spot_with_forecast)
            except Exception as e:
                logger.error(f"Error processing spot {spot.get('name', 'unknown')}: {str(e)}")
                continue
                
        return spots_with_forecast
    except Exception as e:
        logger.error(f"Error loading forecast data: {str(e)}")
        return []

def get_dayList_forecast():
    """Get list of next 7 days for forecast."""
    days = []
    today = datetime.now()
    for i in range(7):
        day = today + timedelta(days=i)
        days.append({
            'display': day.strftime('%A %d').replace('0', ' ').lstrip(),
            'value': day.strftime('%Y-%m-%d')
        })
    return days

def generate_forecast_for_spot(spot: dict, selected_date: str) -> list:
    """
    Generate a complete 7-day forecast for a spot by combining base forecast with conditions analysis.
    Only generates GPT analysis for the selected date to optimize API usage.
    """
    try:
        logger.info(f"[generate_forecast_for_spot] Starting for spot: {spot.get('name')} on date: {selected_date}")
        
        # Get base 7-day forecast
        forecast_data = get_surf_forecast(spot)
        logger.info(f"[generate_forecast_for_spot] Base forecast data: {json.dumps(forecast_data, indent=2) if forecast_data else None}")
        
        if not forecast_data:
            logger.error(f"[generate_forecast_for_spot] Failed to get base forecast for {spot.get('name')}")
            return None
            
        # Get Stormglass data once for all days
        sg_forecasts = get_stormglass_forecast(spot)
        logger.info(f"[generate_forecast_for_spot] Stormglass forecasts: {json.dumps(sg_forecasts, indent=2) if sg_forecasts else None}")
            
        # Enrich each day's forecast with analysis
        for day in forecast_data:
            try:
                # Only generate GPT analysis for selected date
                if day['date'] == selected_date:
                    logger.info(f"[generate_forecast_for_spot] Processing selected date {selected_date} for {spot.get('name')}")
                    
                    # Get Stormglass data for current date
                    forecast_for_day = next((f for f in sg_forecasts if f["date"] == day["date"]), None)
                    if forecast_for_day:
                        # Inject wave and wind direction data
                        day['wave_direction_deg'] = forecast_for_day.get('wave_direction_deg', 270)
                        day['wind_direction_deg'] = forecast_for_day.get('wind_direction_deg', 90)
                        
                        # Check for unsuitable conditions before calling GPT
                        if (forecast_for_day['wave_height_m'] < 0.3 or 
                            forecast_for_day['wind_speed_m_s'] > 10):
                            logger.info(f"[generate_forecast_for_spot] Unsuitable conditions detected for {spot.get('name')}")
                            day['conditions_analysis'] = "Conditions clearly unsuitable: too small or too windy."
                            day['quick_summary'] = "Not surfable today - waves too small or too windy."
                        else:
                            # Add conditions analysis
                            logger.info(f"[generate_forecast_for_spot] Getting conditions analysis for {spot.get('name')}")
                            day['conditions_analysis'] = get_conditions_analysis(spot, day['date'])
                            # Add quick summary
                            logger.info(f"[generate_forecast_for_spot] Getting quick summary for {spot.get('name')}")
                            day['quick_summary'] = get_quick_summary(spot, day)
                            
                            logger.info(f"[generate_forecast_for_spot] Analysis and summary added for {spot.get('name')}:")
                            logger.info(f"Analysis: {day['conditions_analysis']}")
                            logger.info(f"Summary: {day['quick_summary']}")
                    else:
                        logger.warning(f"[generate_forecast_for_spot] No Stormglass data for {spot.get('name')} on {day['date']}")
                        day['wave_direction_deg'] = 'N/A'
                        day['wind_direction_deg'] = 'N/A'
                        day['conditions_analysis'] = None
                        day['quick_summary'] = None
                else:
                    # For non-selected dates, only add Stormglass data if available
                    forecast_for_day = next((f for f in sg_forecasts if f["date"] == day["date"]), None)
                    if forecast_for_day:
                        day['wave_direction_deg'] = forecast_for_day.get('wave_direction_deg', 270)
                        day['wind_direction_deg'] = forecast_for_day.get('wind_direction_deg', 90)
                    else:
                        day['wave_direction_deg'] = 'N/A'
                        day['wind_direction_deg'] = 'N/A'
                    
                    # Set empty values for GPT-related fields
                    day['conditions_analysis'] = None
                    day['quick_summary'] = None
                
            except Exception as e:
                logger.error(f"[generate_forecast_for_spot] Error enriching forecast for {spot.get('name')} on {day.get('date', 'unknown')}: {str(e)}")
                continue
                
        return forecast_data
        
    except Exception as e:
        logger.error(f"[generate_forecast_for_spot] Error for {spot.get('name', 'Unknown')}: {str(e)}")
        return None

@st.cache_data(ttl=21600)  # Cache for 6 hours
def get_stormglass_forecast(spot):
    """
    Retrieves 7-day hourly surf forecast from Stormglass API for a given spot.
    Returns a simplified 7-day daily average forecast list or None on failure.
    """
    try:
        logger.info(f"[Stormglass] Starting API request for spot: {spot.get('name')}")
        base_url = "https://api.stormglass.io/v2/weather/point"
        lat = spot.get("latitude")
        lon = spot.get("longitude")

        params = {
            "lat": lat,
            "lng": lon,
            "params": "waveHeight,wavePeriod,windSpeed,windDirection",
            "source": "noaa",
            "start": int(time.time()),  # now
            "end": int(time.time()) + 7 * 86400  # 7 days ahead
        }

        headers = {"Authorization": STORMGLASS_API_KEY}
        logger.info(f"[Stormglass] Making request for coordinates: {lat}, {lon}")
        response = httpx.get(base_url, params=params, headers=headers, timeout=10)

        if response.status_code != 200:
            logger.error(f"Stormglass API error {response.status_code}: {response.text}")
            return None

        data = response.json().get("hours", [])
        logger.info(f"[Stormglass] Received {len(data)} hours of data for {spot.get('name')}")
        
        if not data:
            logger.warning(f"No Stormglass data returned for {spot.get('name')}")
            return None

        # Group by date and calculate daily averages
        daily_data = {}
        for hour in data:
            date = hour["time"][:10]
            if date not in daily_data:
                daily_data[date] = {
                    "wave_height": [],
                    "wave_period": [],
                    "wind_speed": [],
                    "wind_direction": []
                }
            sg = daily_data[date]
            sg["wave_height"].append(hour["waveHeight"]["noaa"])
            sg["wave_period"].append(hour["wavePeriod"]["noaa"])
            sg["wind_speed"].append(hour["windSpeed"]["noaa"])
            sg["wind_direction"].append(hour["windDirection"]["noaa"])

        # Compute daily averages
        forecasts = []
        for date, values in daily_data.items():
            if not all(values.values()):
                continue
            forecasts.append({
                "date": date,
                "wave_height_m": round(sum(values["wave_height"]) / len(values["wave_height"]), 1),
                "wave_period_s": round(sum(values["wave_period"]) / len(values["wave_period"]), 1),
                "wind_speed_m_s": round(sum(values["wind_speed"]) / len(values["wind_speed"]), 1),
                "wind_direction_deg": round(sum(values["wind_direction"]) / len(values["wind_direction"]), 1)
            })
        
        logger.info(f"[Stormglass] Successfully processed {len(forecasts)} days of forecasts for {spot.get('name')}")
        if forecasts:
            logger.info(f"[Stormglass] Sample forecast data for {spot.get('name')}: {json.dumps(forecasts[0])}")

        return forecasts

    except Exception as e:
        logger.error(f"Error in get_stormglass_forecast for {spot.get('name', 'Unknown')}: {str(e)}")
        return None

if __name__ == "__main__":
    main()
