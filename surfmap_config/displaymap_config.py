
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
    if forecast >=5:
        return 'green'
    if (forecast >= 3.5) and (forecast < 5):
        return 'orange'
    if (forecast >= 1) and (forecast < 3.5):
        return 'red'
    else:
        return 'lightgray'

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
