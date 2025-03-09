import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import os

def test_surf_forecast_scraping(spot_name="penthievre"):
    # Use the same headers as in the main code
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }
    
    # Format the URL
    formatted_name = '-'.join([word.capitalize() for word in spot_name.split('-')])
    url = f"https://www.surf-forecast.com/breaks/{formatted_name}/forecasts/latest/six_day"
    
    print(f"Fetching data from: {url}")
    
    # Make the request
    response = requests.get(url, headers=headers)
    print(f"Response status code: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")
    
    # Check if we got a valid response
    if response.status_code != 200:
        print(f"Error: Got status code {response.status_code}")
        print("Response content:", response.text[:500])  # Print first 500 chars of response
        return response.status_code, {}
    
    # Save the raw HTML
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_filename = f"surf_forecast_response_{timestamp}.html"
    json_filename = f"extracted_data_{timestamp}.json"
    
    # Get absolute paths
    html_path = os.path.abspath(html_filename)
    json_path = os.path.abspath(json_filename)
    
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"\nSaved raw HTML to: {html_path}")
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Check if we got a valid page
    if not soup.find('body'):
        print("Warning: No body tag found in response")
        return response.status_code, {}
    
    # Try to extract data using the same selectors
    data = {}
    
    # Print the structure of the forecast table
    forecast_table = soup.find('table', class_='forecast-table')
    if forecast_table:
        print("\nFound forecast table with structure:")
        print(f"- Number of rows: {len(forecast_table.find_all('tr'))}")
        print(f"- Number of columns: {len(forecast_table.find_all('th'))}")
    else:
        print("\nWARNING: Could not find forecast table!")
        print("Available tables:", [table.get('class', 'no-class') for table in soup.find_all('table')])
    
    # Try to extract the data
    try:
        # Ratings
        rating_images = soup.select('.forecast-table-rating img[alt]')
        data['ratings'] = [img.get('alt', '0') for img in rating_images]
        print("\nRatings found:", data['ratings'])
        print(f"Number of ratings: {len(data['ratings'])}")
        
        # Wave heights
        wave_heights = soup.select('.forecast-table__wave-height .forecast-table__value')
        data['wave_heights'] = [el.text.strip() for el in wave_heights]
        print("\nWave heights found:", data['wave_heights'])
        print(f"Number of wave heights: {len(data['wave_heights'])}")
        
        # Wave periods
        wave_periods = soup.select('.forecast-table__wave-period .forecast-table__value')
        data['wave_periods'] = [el.text.strip() for el in wave_periods]
        print("\nWave periods found:", data['wave_periods'])
        print(f"Number of wave periods: {len(data['wave_periods'])}")
        
        # Wave energy
        wave_energy = soup.select('.forecast-table__wave-energy .forecast-table__value')
        data['wave_energy'] = [el.text.strip() for el in wave_energy]
        print("\nWave energy found:", data['wave_energy'])
        print(f"Number of wave energy values: {len(data['wave_energy'])}")
        
        # Wind speeds
        wind_speeds = soup.select('.forecast-table__wind-speed .forecast-table__value')
        data['wind_speeds'] = [el.text.strip() for el in wind_speeds]
        print("\nWind speeds found:", data['wind_speeds'])
        print(f"Number of wind speeds: {len(data['wind_speeds'])}")
        
        # Print data consistency check
        print("\nData consistency check:")
        for key, values in data.items():
            print(f"{key}: {len(values)} values")
        
    except Exception as e:
        print(f"Error extracting data: {str(e)}")
        print("Full error details:", e.__class__.__name__)
    
    # Save the extracted data
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved extracted data to: {json_path}")
    
    return response.status_code, data

if __name__ == "__main__":
    status_code, data = test_surf_forecast_scraping()
    print(f"\nResponse status code: {status_code}") 