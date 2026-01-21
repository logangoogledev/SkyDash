import discord
from discord import app_commands, ui
import requests
import datetime

# --- CONFIGURATION (Replace these with your actual keys) ---
# It is better to use os.getenv('TOKEN') for security, but you can paste them here for testing.
DISCORD_TOKEN = "YOUR_DISCORD_BOT_TOKEN"
MAPBOX_TOKEN = "YOUR_MAPBOX_PUBLIC_TOKEN"

# WMO Weather Codes mapping to Emojis and Text
WEATHER_MAP = {
    0: ("☀️", "Clear Sky"),
    1: ("🌤️", "Mainly Clear"),
    2: ("⛅", "Partly Cloudy"),
    3: ("☁️", "Overcast"),
    45: ("🌫️", "Foggy"),
    51: ("🌦️", "Light Drizzle"),
    61: ("🌧️", "Rain"),
    71: ("🌨️", "Snow"),
    80: ("🌦️", "Rain Showers"),
    95: ("⛈️", "Thunderstorm"),
}

class WeatherDashboard(ui.View):
    """The interactive component of the dashboard."""
    def __init__(self, location_data, weather_data):
        super().__init__(timeout=300)
        self.loc = location_data
        self.data = weather_data
        self.mode = "current"

    def create_embed(self):
        name = f"{self.loc['name']}, {self.loc.get('country', '')}"
        embed = discord.Embed(color=0x2b2d31) # Discord dark theme color
        
        if self.mode == "current":
            curr = self.data['current']
            code = curr['weather_code']
            icon, condition = WEATHER_MAP.get(code, ("🌡️", "Weather"))
            
            embed.title = f"📍 {name}"
            embed.description = f"### {icon} {condition}"
            
            embed.add_field(name="Temperature", value=f"**{curr['temperature_2m']}°C**", inline=True)
            embed.add_field(name="Feels Like", value=f"{curr['apparent_temperature']}°C", inline=True)
            embed.add_field(name="Wind Speed", value=f"{curr['wind_speed_10m']} km/h", inline=True)
            
            # Mapbox Static Map URL
            map_url = (
                f"https://api.mapbox.com/styles/v1/mapbox/dark-v11/static/"
                f"{self.loc['longitude']},{self.loc['latitude']},9/600x300"
                f"?access_token={MAPBOX_TOKEN}"
            )
            embed.set_image(url=map_url)
            
        else:
            embed.title = f"📅 3-Day Forecast: {name}"
            daily = self.data['daily']
            for i in range(3):
                date_str = daily['time'][i]
                max_t = daily['temperature_2m_max'][i]
                min_t = daily['temperature_2m_min'][i]
                code = daily['weather_code'][i]
                icon, cond = WEATHER_MAP.get(code, ("☁️", "N/A"))
                
                embed.add_field(
                    name=f"🗓️ {date_str}", 
                    value=f"{icon} **{cond}**\nHigh: {max_t}°C | Low: {min_t}°C", 
                    inline=False
                )
        
        embed.set_footer(text="SkyDash • Modern Weather Module")
        embed.timestamp = datetime.datetime.now()
        return embed

    @ui.button(label="Now", style=discord.ButtonStyle.gray, emoji="🏠")
    async def show_current(self, interaction: discord.Interaction, button: ui.Button):
        self.mode = "current"
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @ui.button(label="Forecast", style=discord.ButtonStyle.blurple, emoji="📅")
    async def show_forecast(self, interaction: discord.Interaction, button: ui.Button):
        self.mode = "forecast"
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

class SkyDashBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = SkyDashBot()

@client.tree.command(name="weather", description="Search for weather in a specific location")
@app_commands.describe(location="Type the city or place name (e.g. London, UK)")
async def weather(interaction: discord.Interaction, location: str):
    await interaction.response.defer() # Shows 'Bot is thinking...'

    # 1. Geocoding API (Convert city name to Coordinates)
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
    geo_res = requests.get(geo_url).json()

    if not geo_res.get('results'):
        return await interaction.followup.send(f"❌ Could not find '{location}'. Try being more specific!")

    loc = geo_res['results'][0]

    # 2. Weather API (Get Forecast and Current Data)
    weather_params = {
        "latitude": loc['latitude'],
        "longitude": loc['longitude'],
        "current": ["temperature_2m", "apparent_temperature", "weather_code", "wind_speed_10m"],
        "daily": ["weather_code", "temperature_2m_max", "temperature_2m_min"],
        "timezone": "auto"
    }
    w_res = requests.get("https://api.open-meteo.com/v1/forecast", params=weather_params).json()

    # 3. Send Dashboard
    view = WeatherDashboard(loc, w_res)
    await interaction.followup.send(embed=view.create_embed(), view=view)

@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")
    print("------")

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
