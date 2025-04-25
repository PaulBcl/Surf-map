#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""
return the color following selected criteria

@param: rating ou distance
"""
def color_rating_distance(distance_h):
    if distance_h >=8:
        return 'lightgray'
    if distance_h < 4:
        return 'green'
    if distance_h < 6:
        return 'orange'
    if distance_h < 8:
        return 'red'

def color_rating_forecast(forecast):
    """Return color based on surf forecast rating (0-10)."""
    try:
        forecast = float(forecast)
        if forecast >= 7:
            return 'darkgreen'  # Excellent conditions
        if forecast >= 5:
            return 'green'      # Good conditions
        if forecast >= 3:
            return 'orange'     # Fair conditions
        if forecast > 0:
            return 'red'        # Poor conditions
        return 'lightgray'      # No forecast or zero rating
    except (ValueError, TypeError):
        return 'lightgray'      # Invalid forecast value

def color_rating_prix(prix):
    if prix >=100:
        return 'lightgray'
    if prix < 40:
        return 'green'
    if prix < 70:
        return 'orange'
    if prix < 100:
        return 'red'

def color_rating_criteria(is_option_prix_ok, is_option_distance_h_ok):
    if is_option_prix_ok == True & is_option_distance_h_ok == True:
        return "green"
    if is_option_prix_ok == True or is_option_distance_h_ok == True:
        return "orange"
    if is_option_prix_ok == False & is_option_distance_h_ok == False:
        return "red"
