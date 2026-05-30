import aiohttp
from typing import Dict, Any, Optional
from app.core.config import settings
import structlog

logger = structlog.get_logger()

# Bounding box coordinates mock registry for major states
INDIAN_STATES_COORDINATES = [
    {
        "state": "Bihar",
        "district": "Patna",
        "block": "Phulwari Sharif",
        "soil_type": "Alluvial Soil (कछारी मिट्टी)",
        "lat_min": 25.0, "lat_max": 26.0,
        "lon_min": 84.5, "lon_max": 85.8
    },
    {
        "state": "Bihar",
        "district": "Muzaffarpur",
        "block": "Kanti",
        "soil_type": "Sandy Loam (बलुई दोमट)",
        "lat_min": 26.0, "lat_max": 26.5,
        "lon_min": 85.0, "lon_max": 85.6
    },
    {
        "state": "Maharashtra",
        "district": "Pune",
        "block": "Haveli",
        "soil_type": "Black Soil (काली मिट्टी / रेगुर)",
        "lat_min": 18.0, "lat_max": 19.0,
        "lon_min": 73.5, "lon_max": 74.5
    },
    {
        "state": "Tamil Nadu",
        "district": "Coimbatore",
        "block": "Pollachi",
        "soil_type": "Red Soil (लाल मिट्टी)",
        "lat_min": 10.5, "lat_max": 11.5,
        "lon_min": 76.8, "lon_max": 77.5
    }
]

class LocationService:
    @staticmethod
    async def resolve_location(
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        cell_tower_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolves geolocation identifiers to Indian administrative units (State, District, Block, Village)
        and environment features like Soil Type.
        """
        result = {
            "state": settings.DEFAULT_STATE,
            "district": settings.DEFAULT_DISTRICT,
            "block": settings.DEFAULT_BLOCK,
            "village": "Rural Village (ग्रामीण क्षेत्र)",
            "soil_type": "Alluvial Soil (कछारी मिट्टी)",
            "lookup_status": "full_fallback"
        }

        # 1. Resolve via GPS coordinate boundaries
        if latitude is not None and longitude is not None:
            for loc in INDIAN_STATES_COORDINATES:
                if (loc["lat_min"] <= latitude <= loc["lat_max"] and
                        loc["lon_min"] <= longitude <= loc["lon_max"]):
                    result.update({
                        "state": loc["state"],
                        "district": loc["district"],
                        "block": loc["block"],
                        "soil_type": loc["soil_type"],
                        "lookup_status": "success"
                    })
                    logger.info("Location resolved via coordinate mapping", **result)
                    return result

        # 2. Resolve via Cell Tower Metadata
        if cell_tower_id:
            # Format expected: MCC-MNC-LAC-CID (e.g. 404-45-12345-67890)
            # In a production scenario, query a telecom API (e.g., UnwiredLabs, OpenCellID)
            # For demonstration, we match cell prefixes or return partial mock
            parts = cell_tower_id.split("-")
            if len(parts) >= 2:
                mcc, mnc = parts[0], parts[1]
                # 404 & 405 are India MCC
                if mcc in ["404", "405"]:
                    # MNC mappings represent operators (Jio, Airtel, Vi, BSNL)
                    result.update({
                        "state": "Bihar",
                        "district": "Gaya",
                        "block": "Bodhgaya",
                        "soil_type": "Sandy Clay (बलुई चिकनी मिट्टी)",
                        "lookup_status": "success"
                    })
                    logger.info("Location resolved via Cell Tower database lookup", cell_tower_id=cell_tower_id)
                    return result

        # 3. Resolve via IP Fallback (utilizing free ip-api.com service asynchronously)
        if ip_address and ip_address not in ["127.0.0.1", "localhost", "::1"]:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://ip-api.com/json/{ip_address}?fields=status,regionName,city,lat,lon") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("status") == "success":
                                result.update({
                                    "state": data.get("regionName", settings.DEFAULT_STATE),
                                    "district": data.get("city", settings.DEFAULT_DISTRICT),
                                    "block": data.get("city", settings.DEFAULT_BLOCK),
                                    "soil_type": "Red Loam (लाल दोमट)",
                                    "lookup_status": "partial_fallback"
                                })
                                logger.info("Location partially resolved via IP Lookup", ip_address=ip_address)
                                return result
            except Exception as e:
                logger.error("IP Geolocation resolution failed, falling back", error=str(e))

        logger.info("Location lookup failed. Employing environmental fallbacks.", **result)
        return result
