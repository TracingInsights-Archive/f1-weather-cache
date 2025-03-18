import os
import json
import requests
from datetime import datetime, timedelta

# List of F1 circuit coordinates from your data
CIRCUIT_COORDINATES = [
    (-37.8373, 144.9666),  # Melbourne
    (31.3807, 121.2498),   # Shanghai
    (35.3689, 138.9256),   # Suzuka
    (26.037, 50.5112),     # Sakhir
    (21.485811, 39.192505), # Jeddah
    (25.957764, -80.238835), # Miami
    (44.344576, 11.713808), # Imola
    (43.7338, 7.4215),     # Monaco
    (41.5638, 2.2585),     # Catalunya
    (45.5034, -73.5267),   # Montreal
    (47.2225, 14.7607),    # Spielberg
    (52.0706, -1.0174),    # Silverstone
    (50.444, 5.9687),      # Spa-Francorchamps
    (47.583, 19.2526),     # Budapest
    (52.388408, 4.547122), # Zandvoort
    (45.6169, 9.2825),     # Monza
    (40.3699, 49.8433),    # Baku
    (1.2857, 103.8575),    # Singapore
    (30.1328, -97.6411),   # Austin
    (19.4028, -99.0986),   # Mexico City
    (-23.7014, -46.6969),  # Sao Paulo
    (36.166747, -115.148708), # Las Vegas
    (25.490292, 51.45303), # Doha
    (24.4821, 54.3482),    # Yas Marina
]

def ensure_directory_exists(directory):
    """Ensure the specified directory exists."""
    if not os.path.exists(directory):
        os.makedirs(directory)

def fetch_weather_data(latitude, longitude):
    """Fetch weather data for the given coordinates."""
    # Calculate date range (today + 14 days forecast)
    today = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
    
    # Construct API URL
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=temperature_2m,weathercode,precipitation_probability,precipitation,windspeed_10m,windgusts_10m,visibility,relativehumidity_2m,apparent_temperature&timezone=auto&start_date={today}&end_date={end_date}"
    
    # Make API request
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching data for {latitude},{longitude}: {response.status_code}")
        return None

def main():
    """Main function to update weather cache."""
    # Ensure data directory exists
    data_dir = "data"
    ensure_directory_exists(data_dir)
    
    # Process each circuit
    for lat, lon in CIRCUIT_COORDINATES:
        print(f"Fetching weather data for {lat}, {lon}")
        
        # Format coordinates for filename
        lat_formatted = str(lat).replace('.', '_')
        lon_formatted = str(lon).replace('.', '_')
        filename = f"{lat_formatted}_{lon_formatted}.json"
        filepath = os.path.join(data_dir, filename)
        
        # Fetch weather data
        weather_data = fetch_weather_data(lat, lon)
        
        if weather_data:
            # Add metadata
            weather_data['metadata'] = {
                'cached_at': datetime.now().isoformat(),
                'latitude': lat,
                'longitude': lon
            }
            
            # Save to file
            with open(filepath, 'w') as f:
                json.dump(weather_data, f, indent=2)
            
            print(f"Saved weather data to {filepath}")
        else:
            print(f"Failed to fetch weather data for {lat}, {lon}")

if __name__ == "__main__":
    main()
