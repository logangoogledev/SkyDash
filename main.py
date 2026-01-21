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

user_settings = {} 

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
        </div>
    </body>
    """

def run_web(): 
    app.run(host='0.0.0.0', port=10000)

# --- DASHBOARD CLASS (Must be defined BEFORE the command) ---
class WeatherDashboard(ui.View):
    def __init__(self, loc, data, user_id):
        super().__init__(timeout=300)
        self.loc = loc
        self.data = data
        self.user_id = user_id
        self.mode = "current"

    def get_unit_pref(self):
        return user_settings.get(self.user_id, {"units": "metric"})["units"]

    def create_embed(self):
        units = self.get_unit_pref()
        temp_unit = "°C" if units == "metric" else "°F"
        wind_unit = "km/h" if units == "metric" else "mph"
        
        embed = discord.Embed(color=0x2b2d31, timestamp=datetime.datetime.now())
        name = self.loc['name']

        if self.mode == "current":
            curr = self.data['current']
            icon, cond = WEATHER_MAP.get(curr['weather_code'], ("🌡️", "Weather"))
            embed.title = f"📍 {name}"
            embed.description = f"### {icon} {cond}"
            embed.add_field(name="Temp", value=f"**{curr['temperature_2m']}{temp_unit}**", inline=True)
            embed.add_field(name="Wind", value=f"{curr['wind_speed_10m']} {wind_unit}", inline=True)
            
            map_url = f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/{self.loc['longitude']},{self.loc['latitude']},9/600x300?access_token={MAPBOX_TOKEN}"
            embed.set_image(url=map_url)
        else:
            embed.title = f"📅 3-Day Forecast: {name}"
            daily = self.data['daily']
            for i in range(min(3, len(daily['time']))):
                icon, cond = WEATHER_MAP.get(daily['weather_code'][i], ("☁️", "N/A"))
                embed.add_field(name=daily['time'][i], value=f"{icon} **{cond}**\nMax: {daily['temperature_2m_max'][i]}{temp_unit}", inline=False)

        embed.set_footer(text=f"Units: {units.capitalize()}")
        return embed

    @ui.button(label="Refresh", style=discord.ButtonStyle.gray, emoji="🔄")
    async def refresh(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(embed=self.create_embed())

    @ui.button(label="Switch View", style=discord.ButtonStyle.blurple, emoji="📅")
    async def forecast(self, interaction: discord.Interaction, button: ui.Button):
        self.mode = "forecast" if self.mode == "current" else "current"
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @ui.button(label="Toggle Units", style=discord.ButtonStyle.green, emoji="⚙️")
    async def toggle_units(self, interaction: discord.Interaction, button: ui.Button):
        current = self.get_unit_pref()
        new_unit = "imperial" if current == "metric" else "metric"
        user_settings[self.user_id] = {"units": new_unit}
        await interaction.response.send_message(f"✅ Units toggled to **{new_unit}**. Refresh or re-run command!", ephemeral=True)

# --- BOT SETUP ---
class SkyDash(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
    async def setup_hook(self): 
        await self.tree.sync()

client = SkyDash()

# --- AUTOCOMPLETE ---
@client.tree.command(name="weather", description="SkyDash Visual Dashboard")
async def weather(interaction: discord.Interaction, location: str):
    await interaction.response.defer()
    
    try:
        if "|" in location:
            lat, lon, display_name = location.split('|')
            lat, lon = float(lat), float(lon)
        else:
            geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1").json()
            loc = geo['results'][0]
            lat, lon, display_name = loc['latitude'], loc['longitude'], loc['name']
    except:
        return await interaction.followup.send("❌ Location error. Please use the suggestions!")

    units = user_settings.get(interaction.user.id, {"units": "metric"})["units"]
    params = {
        "latitude": lat, "longitude": lon,
        "current": ["temperature_2m", "weather_code", "wind_speed_10m"],
        "daily": ["weather_code", "temperature_2m_max"],
        "temperature_unit": "fahrenheit" if units == "imperial" else "celsius",
        "timezone": "auto"
    }
    data = requests.get("https://api.open-meteo.com/v1/forecast", params=params).json()

    loc_obj = {"name": display_name, "latitude": lat, "longitude": lon}
    view = WeatherDashboard(loc_obj, data, interaction.user.id)
    await interaction.followup.send(embed=view.create_embed(), view=view)

@weather.autocomplete('location')
async def location_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    if len(current) < 3: return []
    
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={current}&count=5"
    try:
        response = requests.get(url, timeout=2).json()
        results = response.get('results', [])
        choices = []
        for loc in results:
            admin = loc.get('admin1', '')
            full_name = f"{loc['name']}, {admin}, {loc['country']}" if admin else f"{loc['name']}, {loc['country']}"
            value = f"{loc['latitude']}|{loc['longitude']}|{full_name}"
            choices.append(app_commands.Choice(name=full_name[:100], value=value[:100]))
        return choices
    except:
        return []

@client.event
async def on_ready():
    print(f"✅ {client.user} is live.")

if __name__ == "__main__":
    Thread(target=run_web).start()
    client.run(DISCORD_TOKEN)
