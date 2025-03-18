import os
import json
import requests
import asyncio
import aiohttp
from datetime import datetime, timedelta
import time

# List of F1 circuit coordinates
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

async def fetch_weather_data(session, latitude, longitude):
    """Fetch weather data for the given coordinates asynchronously."""
    # Calculate date range (today + 14 days forecast)
    today = datetime.now().strftime('%Y-%m-%d')
    end_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')

    # Construct API URL with both minutely_15 and hourly data for better coverage
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&minutely_15=temperature_2m,weathercode,precipitation_probability,precipitation,windspeed_10m,windgusts_10m,visibility,relativehumidity_2m,apparent_temperature,cloudcover,winddirection_10m&hourly=temperature_2m,weathercode,precipitation_probability,precipitation,windspeed_10m,windgusts_10m,visibility,relativehumidity_2m,apparent_temperature,cloudcover,winddirection_10m&timezone=auto&start_date={today}&end_date={end_date}"
    
    try:
        # Make API request with timeout and retry logic
        for attempt in range(3):  # Try up to 3 times
            try:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Define all fields that need default values
                        all_fields = [
                            'temperature_2m', 'weathercode', 'precipitation_probability', 
                            'precipitation', 'windspeed_10m', 'windgusts_10m', 'visibility',
                            'relativehumidity_2m', 'apparent_temperature', 'cloudcover', 
                            'winddirection_10m'
                        ]
                        
                        # Process minutely_15 data if available
                        if 'minutely_15' in data:
                            # Add a flag to indicate we have minutely data
                            data['hasMinutelyData'] = True
                            
                            # Ensure all fields exist with default values
                            for field in all_fields:
                                if field not in data['minutely_15'] or not data['minutely_15'][field]:
                                    # Set appropriate default values
                                    default_value = 0
                                    if field == 'visibility':
                                        default_value = 10000  # 10km visibility
                                    
                                    data['minutely_15'][field] = [default_value] * len(data['minutely_15']['time'])
                        else:
                            data['hasMinutelyData'] = False
                        
                        # Process hourly data (always available)
                        if 'hourly' in data:
                            for field in all_fields:
                                if field not in data['hourly'] or not data['hourly'][field]:
                                    # Set appropriate default values
                                    default_value = 0
                                    if field == 'visibility':
                                        default_value = 10000  # 10km visibility
                                    
                                    data['hourly'][field] = [default_value] * len(data['hourly']['time'])
                        
                        # Interpolate missing data from hourly to minutely if needed
                        if 'minutely_15' in data and 'hourly' in data:
                            minutely_times = [datetime.fromisoformat(t.replace('Z', '+00:00')) for t in data['minutely_15']['time']]
                            hourly_times = [datetime.fromisoformat(t.replace('Z', '+00:00')) for t in data['hourly']['time']]
                            
                            for field in all_fields:
                                # Skip if minutely data is already complete
                                if field in data['minutely_15'] and all(v is not None for v in data['minutely_15'][field]):
                                    continue
                                
                                # If field is missing in minutely but present in hourly, interpolate
                                if (field not in data['minutely_15'] or not data['minutely_15'][field]) and field in data['hourly']:
                                    # Create a new array for interpolated values
                                    interpolated = []
                                    
                                    for m_time in minutely_times:
                                        # Find the closest hourly time points
                                        closest_idx = min(range(len(hourly_times)), 
                                                         key=lambda i: abs((hourly_times[i] - m_time).total_seconds()))
                                        
                                        # Use the closest hourly value
                                        if closest_idx < len(data['hourly'][field]):
                                            interpolated.append(data['hourly'][field][closest_idx])
                                        else:
                                            interpolated.append(0)  # Default if out of range
                                    
                                    # Update the minutely data with interpolated values
                                    data['minutely_15'][field] = interpolated
                        
                        return data
                    elif response.status == 429:  # Rate limit
                        wait_time = 2 ** attempt  # Exponential backoff
                        print(f"Rate limited, waiting {wait_time}s before retry")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"Error fetching data for {latitude},{longitude}: {response.status}")
                        return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"Request error (attempt {attempt+1}/3): {e}")
                await asyncio.sleep(1)

        return None  # All attempts failed
    except Exception as e:
        print(f"Unexpected error for {latitude},{longitude}: {e}")
        return None

async def main():
    """Main function to update weather cache asynchronously."""
    start_time = time.time()

    # Ensure data directory exists
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # Set up async session with connection pooling
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=5)) as session:
        # Create tasks for all circuits
        tasks = []
        for lat, lon in CIRCUIT_COORDINATES:
            tasks.append(fetch_weather_data(session, lat, lon))

        # Execute all tasks concurrently with progress reporting
        print(f"Fetching weather data for {len(tasks)} circuits...")
        results = await asyncio.gather(*tasks)

        # Process results and save to files
        for (lat, lon), weather_data in zip(CIRCUIT_COORDINATES, results):
            if weather_data:
                # Format coordinates for filename
                lat_formatted = str(lat).replace('.', '_')
                lon_formatted = str(lon).replace('.', '_')
                filename = f"{lat_formatted}_{lon_formatted}.json"
                filepath = os.path.join(data_dir, filename)

                # Add metadata
                weather_data['metadata'] = {
                    'cached_at': datetime.now().isoformat(),
                    'latitude': lat,
                    'longitude': lon
                }

                # Save to file
                with open(filepath, 'w') as f:
                    json.dump(weather_data, f, indent=2)

                print(f"Saved weather data for {lat}, {lon}")
            else:
                print(f"Failed to fetch weather data for {lat}, {lon}")

    elapsed_time = time.time() - start_time
    print(f"Weather cache update completed in {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
