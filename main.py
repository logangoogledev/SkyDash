import discord
from discord import app_commands, ui
import requests
import os
from flask import Flask
from threading import Thread
import datetime
from typing import List

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

user_settings = {} # {user_id: {"units": "metric"}}

WEATHER_MAP = {
    0: ("☀️", "Clear Sky"), 1: ("🌤️", "Mainly Clear"), 2: ("⛅", "Partly Cloudy"),
    3: ("☁️", "Overcast"), 45: ("🌫️", "Foggy"), 51: ("🌦️", "Light Drizzle"),
    61: ("🌧️", "Rain"), 71: ("🌨️", "Snow"), 95: ("⛈️", "Thunderstorm")
}

# --- DUMMY WEB SERVER ---
app = Flask('')
@app.route('/')
def home():
    return """
    <body style="font-family:sans-serif;background:#1e2124;color:white;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
        <div style="text-align:center;border:1px solid #7289da;padding:40px;border-radius:10px;">
            <h1 style="color:#7289da;">🛰️ SkyDash Status</h1>
            <p>Status: <span style="color:#43b581;">● Online</span></p>
            <hr style="border:0.5px solid #444;">
            <p><b>/weather [city]</b> - Dashboard with Autocomplete</p>
            <p><b>/about</b> - System Info</p>
        </div>
    </body>
    """

def run_web(): app.run(host='0.0.0.0', port=10000)

# --- BOT SETUP ---
class SkyDash(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
    async def setup_hook(self): await self.tree.sync()

client = SkyDash()

# --- AUTOCOMPLETE LOGIC ---
async def location_autocomplete(
    interaction: discord.Interaction, 
    current: str
) -> List[app_commands.Choice[str]]:
    if len(current) < 3:
        return [] # Don't search until at least 3 characters are typed

    # Query the Geocoding API
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={current}&count=10&language=en&format=json"
    try:
        response = requests.get(url, timeout=2).json()
        results = response.get('results', [])
    except:
        return []

    choices = []
    for loc in results:
        name = loc.get('name')
        admin1 = loc.get('admin1', '') # State/Province
        country = loc.get('country', '')
        
        # Format the display: "Londonderry, New Hampshire, US"
        display_name = f"{name}, {admin1}, {country}" if admin1 else f"{name}, {country}"
        
        # Limit to 100 chars (Discord requirement)
        if len(display_name) > 100: display_name = display_name[:97] + "..."
        
        # The 'value' is what the bot receives (we'll use coordinates to be precise)
        coords = f"{loc['latitude']}|{loc['longitude']}|{display_name}"
        choices.append(app_commands.Choice(name=display_name, value=coords))
        
    return choices

# --- THE COMMAND ---
@client.tree.command(name="weather", description="SkyDash Visual Dashboard")
@app_commands.autocomplete(location=location_autocomplete)
async def weather(interaction: discord.Interaction, location: str):
    await interaction.response.defer()
    
    # Parse the hidden coordinate data from autocomplete
    try:
        lat, lon, display_name = location.split('|')
        lat, lon = float(lat), float(lon)
    except ValueError:
        # Fallback if user types manually without selecting from autocomplete
        geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1").json()
        if not geo.get('results'): return await interaction.followup.send("❌ Location not found.")
        loc = geo['results'][0]
        lat, lon, display_name = loc['latitude'], loc['longitude'], loc['name']

    # Weather API Fetching
    units = user_settings.get(interaction.user.id, {"units": "metric"})["units"]
    params = {
        "latitude": lat, "longitude": lon,
        "current": ["temperature_2m", "weather_code", "wind_speed_10m"],
        "daily": ["weather_code", "temperature_2m_max"],
        "temperature_unit": "fahrenheit" if units == "imperial" else "celsius",
        "timezone": "auto"
    }
    data = requests.get("https://api.open-meteo.com/v1/forecast", params=params).json()

    # Create the dashboard (using previous WeatherDashboard class)
    # [Note: Insert the WeatherDashboard class code here from the previous message]
    loc_obj = {"name": display_name, "latitude": lat, "longitude": lon}
    view = WeatherDashboard(loc_obj, data, interaction.user.id)
    await interaction.followup.send(embed=view.create_embed(), view=view)

if __name__ == "__main__":
    Thread(target=run_web).start()
    client.run(DISCORD_TOKEN)
