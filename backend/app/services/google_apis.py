"""
Google Maps, Geocoding, Address Validation and Air Quality API Integration Service
"""
import httpx
from typing import Dict, Any, Optional
from app.utils.retry import async_retry
import structlog
from app.config import get_settings

logger = structlog.get_logger()

# Realistic fallback mock location in Bengaluru for festive sweets delivery
MOCK_BENGALURU_COORDS = {
    "formatted_address": "12th Cross Rd, Malleshwaram, Bengaluru, Karnataka 560003, India",
    "latitude": 13.0033,
    "longitude": 77.5694,
    "validation_status": "validated",
    "is_mock": True
}

class GoogleMapsService:
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.google_maps_api_key

    @async_retry(max_attempts=2, delay=1.0)
    async def validate_address(self, address_text: str) -> Dict[str, Any]:
        """
        Google Address Validation API
        POST https://addressvalidation.googleapis.com/v1:validateAddress?key={api_key}
        """
        if not self.settings.has_google_maps:
            logger.info("Using Google Address Validation mock fallback (no GOOGLE_MAPS_API_KEY)")
            return {
                "validated_address": f"{address_text.strip()}, Verified Postal Area",
                "validation_status": "validated",
                "latitude": 13.0033,
                "longitude": 77.5694,
                "geocoding_status": "OK",
                "validation_details": {
                    "granularity": "PREMISE",
                    "formattedAddress": f"{address_text}, Bengaluru, Karnataka 560003",
                    "confirmed": True
                },
                "is_mock": True
            }

        url = f"https://addressvalidation.googleapis.com/v1:validateAddress?key={self.api_key}"
        payload = {
            "address": {
                "addressLines": [address_text],
                "regionCode": "IN"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()

                result = data.get("result", {})
                verdict = result.get("verdict", {})
                geocode = result.get("geocode", {})
                location = geocode.get("location", {})

                val_status = "validated" if verdict.get("hasUnconfirmedComponents") is False else "partial_match"

                return {
                    "validated_address": result.get("address", {}).get("formattedAddress", address_text),
                    "validation_status": val_status,
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "geocoding_status": "OK" if location else "PARTIAL",
                    "validation_details": verdict,
                    "is_mock": False
                }
        except Exception as e:
            logger.error("Google Address Validation API error", error=str(e))
            return {
                "validated_address": address_text,
                "validation_status": "partial_match",
                "latitude": 13.0033,
                "longitude": 77.5694,
                "geocoding_status": "ERROR_FALLBACK",
                "validation_details": {"error": str(e)},
                "is_mock": True
            }

    async def geocode_address(self, address_text: str) -> Dict[str, Any]:
        """
        Google Geocoding API
        """
        if not self.settings.has_google_maps:
            return MOCK_BENGALURU_COORDS

        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address_text}&key={self.api_key}&region=in"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url)
                res.raise_for_status()
                data = res.json()
                results = data.get("results", [])
                if results:
                    loc = results[0]["geometry"]["location"]
                    return {
                        "formatted_address": results[0]["formatted_address"],
                        "latitude": loc["lat"],
                        "longitude": loc["lng"],
                        "validation_status": "validated",
                        "is_mock": False
                    }
        except Exception as e:
            logger.error("Geocoding failed", error=str(e))

        return MOCK_BENGALURU_COORDS

    async def get_air_quality(self, lat: float, lng: float) -> Dict[str, Any]:
        """
        Google Air Quality API
        Contextual delivery planning info only
        """
        disclaimer = "Air quality data is provided as contextual delivery-planning information only. It does not constitute proof that a delivery is safe or unsafe."

        if not self.settings.has_google_maps:
            # Typical moderate winter festive AQI in Indian urban metro
            return {
                "aqi_value": 115,
                "aqi_category": "Moderate Air Quality",
                "dominant_pollutant": "pm25",
                "health_recommendations": "Elderly and riders with respiratory sensitivity may consider masks during peak traffic.",
                "location": f"Coordinates ({lat:.4f}, {lng:.4f})",
                "is_mock": True,
                "disclaimer": disclaimer
            }

        url = f"https://airquality.googleapis.com/v1/currentConditions:lookup?key={self.api_key}"
        payload = {
            "location": {"latitude": lat, "longitude": lng},
            "languageCode": "en"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, json=payload)
                res.raise_for_status()
                data = res.json()
                indexes = data.get("indexes", [])
                aqi = 85
                cat = "Moderate"
                pollutant = "pm25"
                if indexes:
                    aqi = indexes[0].get("aqi", 85)
                    cat = indexes[0].get("category", "Moderate")
                    pollutant = indexes[0].get("dominantPollutant", "pm25")

                return {
                    "aqi_value": aqi,
                    "aqi_category": cat,
                    "dominant_pollutant": pollutant,
                    "health_recommendations": "Standard operational delivery precautions.",
                    "location": f"Lat {lat}, Lng {lng}",
                    "is_mock": False,
                    "disclaimer": disclaimer
                }
        except Exception as e:
            logger.error("Air Quality API call failed", error=str(e))
            return {
                "aqi_value": 95,
                "aqi_category": "Moderate",
                "dominant_pollutant": "pm25",
                "health_recommendations": "Advisory not available",
                "is_mock": True,
                "disclaimer": disclaimer
            }

google_maps_service = GoogleMapsService()
