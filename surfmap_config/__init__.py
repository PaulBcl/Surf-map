from . import forecast_config
from . import api_config
from . import displaymap_config

# Re-export all functions for backward compatibility
from .forecast_config import (
    get_coordinates,
    get_surf_forecast,
    analyze_spot_conditions,
    get_conditions_analysis,
    calculate_spot_rating,
    load_lisbon_spots,
    get_spot_forecast,
    load_forecast_data,
    get_dayList_forecast
)

from .api_config import (
    get_google_results,
    get_google_route_info,
    get_route_info,
    google_results,
    df_geocoding
)

from .displaymap_config import (
    color_rating_distance,
    color_rating_forecast,
    color_rating_prix,
    color_rating_criteria
) 