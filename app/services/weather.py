import datetime
import aiohttp
from typing import Dict, Any
from app.core.config import settings
import structlog

logger = structlog.get_logger()

class WeatherService:
    @staticmethod
    def get_current_season() -> str:
        """
        Determines the current agricultural season in India based on month.
        - Kharif: June - October
        - Rabi: November - March
        - Zaid: April - May
        """
        month = datetime.datetime.now().month
        if 6 <= month <= 10:
            return "Kharif (खरीफ)"
        elif month >= 11 or month <= 3:
            return "Rabi (रबी)"
        else:
            return "Zaid (जायद)"

    @classmethod
    async def get_weather(cls, latitude: float, longitude: float) -> Dict[str, Any]:
        """
        Fetches current weather and enrichment parameters using OpenWeatherMap API
        or dynamically generates parameters matching regional standards.
        """
        season = cls.get_current_season()
        
        # Default dynamic generation depending on season
        month = datetime.datetime.now().month
        if "Kharif" in season:
            temp, humidity, rainfall = 30.5, 82.0, "Heavy Rainfall"
        elif "Rabi" in season:
            temp, humidity, rainfall = 18.0, 50.0, "No Rainfall"
        else:
            temp, humidity, rainfall = 38.5, 35.0, "Light Showers"

        result = {
            "temperature": temp,
            "humidity": humidity,
            "rainfall_estimate": rainfall,
            "active_season": season,
            "source": "dynamic_fallback"
        }

        # Query OpenWeatherMap if key is provided
        api_key = settings.OPENWEATHERMAP_API_KEY
        if api_key and api_key != "your_openweathermap_api_key_here":
            try:
                url = f"https://api.openweathermap.org/data/2.5/weather?lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            main = data.get("main", {})
                            rain = data.get("rain", {}).get("1h", 0.0)
                            rain_desc = "No Rainfall"
                            if rain > 5.0:
                                rain_desc = "Heavy Rainfall"
                            elif rain > 1.0:
                                rain_desc = "Moderate Rainfall"
                            elif rain > 0.0:
                                rain_desc = "Light Rainfall"

                            result.update({
                                "temperature": main.get("temp", temp),
                                "humidity": main.get("humidity", humidity),
                                "rainfall_estimate": rain_desc,
                                "source": "open_weather_map"
                            })
                            logger.info("Weather successfully retrieved from OpenWeatherMap", latitude=latitude, longitude=longitude)
                            return result
            except Exception as e:
                logger.error("OpenWeatherMap retrieval error. Using fallback telemetry.", error=str(e))
        
        logger.info("Using local seasonal weather prediction", season=season, latitude=latitude, longitude=longitude)
        return result
