#!/usr/bin/env python
# coding: utf-8

# ### Fonction de geocoding

# Source : https://www.shanelynn.ie/batch-geocoding-in-python-with-google-geocoding-api/

import requests

def get_google_results(address, api_key = None, return_full_response = False):
    try:
        """
        Get geocode results from Google Maps Geocoding API.

        Note, that in the case of multiple google geocode reuslts, this function returns details of the FIRST result.

        @param address: String address as accurate as possible. For Example "18 Grafton Street, Dublin, Ireland"
        @param api_key: String API key if present from google.
                        If supplied, requests will use your allowance from the Google API. If not, you
                        will be limited to the free usage of 2500 requests per day.
        @param return_full_response: Boolean to indicate if you'd like to return the full response from google. This
                        is useful if you'd like additional location details for storage or parsing later.
        """
        # Set up your Geocoding url
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json?address={}".format(address)
        if api_key is not None:
            geocode_url = geocode_url + "&key={}".format(api_key)

        # Ping google for the reuslts:
        results = requests.get(geocode_url)
        # Results will be in JSON format - convert to dict using requests functionality
        results = results.json()

        # if there's no results or an error, return empty results.
        if len(results['results']) == 0:
            output = {
                "formatted_address" : None,
                "latitude": None,
                "longitude": None,
                "accuracy": None,
                "google_place_id": None,
                "type": None,
                "postcode": None
            }
        else:
            answer = results['results'][0]
            output = {
                "formatted_address" : answer.get('formatted_address'),
                "latitude": answer.get('geometry').get('location').get('lat'),
                "longitude": answer.get('geometry').get('location').get('lng'),
                "accuracy": answer.get('geometry').get('location_type'),
                "google_place_id": answer.get("place_id"),
                "type": ",".join(answer.get('types')),
                "postcode": ",".join([x['long_name'] for x in answer.get('address_components')
                                      if 'postal_code' in x.get('types')])
            }

        # Append some other details:
        output['input_string'] = address
        output['number_of_results'] = len(results['results'])
        output['status'] = results.get('status')
        if return_full_response is True:
            output['response'] = results
    except Error as e:
        print("Google results didn't work")
        print(e)
    return output

def get_google_distance(address1, address2, api_key = None):
    """
    Get distance between 2 positition from Google Maps Geocoding API.

    @param address1 List containing longitude & latitude of the address #1
    @param address2 List containing longitude & latitude of the address #2
    @param api_key: String API key if present from google.
    """
    now = datetime.now()
    direction_results = gmaps.directions([address1[0] + "," + address1[1]], [address2[0] + "," + address2[1]],
                            mode = 'driving')
    return direction_results

# Même fonction que get_google_results mais qui tourne sur un df (et gère les erreurs)
def google_results(df_to_search, gmaps_api_key):
    df_google_results = []
    for address in df_to_search:
        try:
            geocode_result = get_google_results(address, gmaps_api_key, return_full_response = True)
            df_google_results.append(geocode_result)
        except Exception as e:
            logger.exception(e)
            logger.error("Major error with {}".format(address))
            logger.error("Skipping!")
    return df_google_results
