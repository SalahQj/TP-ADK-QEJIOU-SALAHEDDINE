"""
Tools module for multi-agent AI system.
Implements tools that can be used by sub-agents.
"""
import os
import requests
from typing import Dict, Any, Optional, List
from . import config


def search_city_info(city: str) -> dict:
    """
    Search for information about a city using Tavily API.
    
    Args:
        city: Name of the city to search for
        
    Returns:
        Dictionary with city information from web search
    """
    api_key = os.getenv("TAVILY_API_KEY")
    
    if not api_key:
        return {"error": "TAVILY_API_KEY not set in .env file"}
    
    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": f"interesting facts about {city} city tourist information",
            "search_depth": "basic",
            "include_answer": True,
            "max_results": 5
        }
        
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Extract the answer and sources
        result = {
            "city": city,
            "summary": data.get("answer", "No summary available"),
            "sources": []
        }
        
        # Get top 3 sources
        for source in data.get("results", [])[:3]:
            result["sources"].append({
                "title": source.get("title", ""),
                "url": source.get("url", ""),
                "content": source.get("content", "")[:200]  # Truncate content
            })
        
        return result
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Tavily API error: {str(e)}", "city": city}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}", "city": city}


def get_public_holidays(country_code: str, year: int = 2025) -> List[dict]:
    """
    Get public holidays for a country using Nager.Date API (free, no API key).
    
    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'MA' for Morocco, 'FR' for France, 'US' for USA)
        year: Year to get holidays for (default: 2025)
        
    Returns:
        List of public holidays with date, name, and type
    """
    try:
        url = f"https://date.nager.at/api/v3/publicholidays/{year}/{country_code.upper()}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        holidays = response.json()
        
        # Format the holidays for better readability
        result = []
        for holiday in holidays:
            result.append({
                "date": holiday.get("date", ""),
                "name": holiday.get("localName", holiday.get("name", "")),
                "name_english": holiday.get("name", ""),
                "fixed": holiday.get("fixed", False),
                "type": ", ".join(holiday.get("types", []))
            })
        
        return result
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return [{"error": f"Country code '{country_code}' not found. Use ISO 3166-1 alpha-2 codes like: MA (Morocco), FR (France), US (USA), DE (Germany), GB (UK), JP (Japan)"}]
        return [{"error": f"HTTP error: {str(e)}"}]
    except Exception as e:
        return [{"error": f"Unexpected error: {str(e)}"}]


def get_weather(city: str) -> dict:
    """
    Get current weather data for a city using Open-Meteo API (free, no API key).
    
    Args:
        city: Name of the city
        
    Returns:
        Weather data with temperature, condition, and description
    """
    try:
        # Step 1: Get coordinates from city name using Open-Meteo Geocoding
        geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        geocode_params = {"name": city, "count": 1, "language": "en"}
        
        geo_response = requests.get(geocode_url, params=geocode_params, timeout=10)
        geo_response.raise_for_status()
        geo_data = geo_response.json()
        
        if "results" not in geo_data or len(geo_data["results"]) == 0:
            return {"error": f"City '{city}' not found"}
        
        lat = geo_data["results"][0]["latitude"]
        lon = geo_data["results"][0]["longitude"]
        city_name = geo_data["results"][0]["name"]
        country = geo_data["results"][0].get("country", "")
        
        # Step 2: Get weather data
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m",
            "timezone": "auto"
        }
        
        weather_response = requests.get(weather_url, params=weather_params, timeout=10)
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        
        current = weather_data.get("current", {})
        temp = current.get("temperature_2m", 0)
        weather_code = current.get("weather_code", 0)
        wind = current.get("wind_speed_10m", 0)
        humidity = current.get("relative_humidity_2m", 0)
        
        # Convert weather code to condition
        condition, description = _get_weather_description(weather_code)
        
        return {
            "city": city_name,
            "country": country,
            "temperature": temp,
            "temperature_unit": "°C",
            "condition": condition,
            "description": description,
            "wind_speed": wind,
            "wind_unit": "km/h",
            "humidity": humidity
        }
        
    except Exception as e:
        # Fallback to mock data if API fails
        return {
            "city": city,
            "temperature": 20,
            "condition": "Unknown",
            "description": f"Could not fetch weather: {str(e)}"
        }


def _get_weather_description(code: int) -> tuple:
    """Convert WMO weather code to human-readable condition."""
    weather_codes = {
        0: ("Clear", "Clear sky"),
        1: ("Mostly Clear", "Mainly clear"),
        2: ("Partly Cloudy", "Partly cloudy"),
        3: ("Cloudy", "Overcast"),
        45: ("Foggy", "Fog"),
        48: ("Foggy", "Depositing rime fog"),
        51: ("Light Drizzle", "Light drizzle"),
        53: ("Drizzle", "Moderate drizzle"),
        55: ("Heavy Drizzle", "Dense drizzle"),
        61: ("Light Rain", "Slight rain"),
        63: ("Rain", "Moderate rain"),
        65: ("Heavy Rain", "Heavy rain"),
        71: ("Light Snow", "Slight snow"),
        73: ("Snow", "Moderate snow"),
        75: ("Heavy Snow", "Heavy snow"),
        80: ("Light Showers", "Slight rain showers"),
        81: ("Showers", "Moderate rain showers"),
        82: ("Heavy Showers", "Violent rain showers"),
        95: ("Thunderstorm", "Thunderstorm"),
        96: ("Thunderstorm", "Thunderstorm with slight hail"),
        99: ("Severe Thunderstorm", "Thunderstorm with heavy hail"),
    }
    return weather_codes.get(code, ("Unknown", "Unknown conditions"))


def search_scholarships(country: str, field: str, level: str) -> List[dict]:
    """
    Search for scholarships using the Scholarships API with fallback mock data.
    
    Args:
        country: User's country of origin
        field: Field of study (e.g., Computer Science, Medicine)
        level: Study level (bachelor, master, phd)
    
    Returns:
        List of matching scholarships
    """
    try:
        # Call the real Scholarships API || not working at the moment 
        url = "https://scholarshipsapi.com/search"
        params = {
            "country": country.lower(),
            "level": level.lower()
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Return the scholarships from the API
        if isinstance(data, list) and len(data) > 0:
            return data
        elif isinstance(data, dict) and "scholarships" in data:
            return data["scholarships"]
            
    except Exception:
        pass  # Fall through to mock data
    
    # Fallback: Return mock scholarships based on country
    return _get_mock_scholarships(country, field, level)


def _get_mock_scholarships(country: str, field: str, level: str) -> List[dict]:
    """Fallback mock scholarship data."""
    country_lower = country.lower()
    
    # Country-specific scholarships
    scholarships = {
        "france": [
            {"name": "Eiffel Excellence Scholarship", "amount": "€1,700/month + tuition", "deadline": "January 10, 2025", "requirements": "Under 25 for Master's, excellent academics", "description": "French government scholarship for international students"},
            {"name": "Émile Boutmy Scholarship (Sciences Po)", "amount": "€5,000-10,000/year", "deadline": "February 23, 2025", "requirements": "Non-EU, excellent academic record", "description": "For undergraduate and master's students at Sciences Po Paris"},
            {"name": "ENS Paris-Saclay International Scholarship", "amount": "€1,000/month", "deadline": "December 1, 2024", "requirements": "Master's level, research focus", "description": "For international students in sciences"},
            {"name": "HEC Paris MBA Scholarship", "amount": "Up to €30,000", "deadline": "Rolling", "requirements": "MBA admission, leadership experience", "description": "Merit-based scholarship for MBA students"},
            {"name": "INSEAD Scholarship", "amount": "€10,000-50,000", "deadline": "Rolling", "requirements": "MBA/Master's admission", "description": "Various scholarships for INSEAD programs"},
        ],
        "qatar": [
            {"name": "Qatar Foundation Scholarship", "amount": "Full tuition + living expenses", "deadline": "February 28, 2025", "requirements": "Excellent academics, leadership", "description": "For international students studying in Qatar"},
            {"name": "Hamad Bin Khalifa University Scholarship", "amount": "Full funding + stipend", "deadline": "March 1, 2025", "requirements": "Admission to HBKU program", "description": "For graduate studies at HBKU"},
            {"name": "Qatar National Research Fund", "amount": "$50,000 grant", "deadline": "April 30, 2025", "requirements": "Research proposal, PhD level", "description": "For doctoral research in Qatar"},
            {"name": "Texas A&M Qatar Scholarship", "amount": "Full tuition", "deadline": "January 15, 2025", "requirements": "Engineering students", "description": "For engineering programs at Texas A&M Qatar"},
            {"name": "Carnegie Mellon Qatar Scholarship", "amount": "Partial to full tuition", "deadline": "January 1, 2025", "requirements": "CS/Business admission", "description": "Merit-based for CMU Qatar students"},
        ],
        "morocco": [
            {"name": "Fulbright Morocco Scholarship", "amount": "Full funding", "deadline": "February 1, 2025", "requirements": "Moroccan citizen, leadership", "description": "US government scholarship for graduate studies"},
            {"name": "Chevening Scholarship", "amount": "Full tuition + £1,200/month", "deadline": "November 7, 2025", "requirements": "2+ years work experience", "description": "UK government scholarship"},
            {"name": "DAAD Germany Scholarship", "amount": "€934/month", "deadline": "October 15, 2025", "requirements": "Good academics, English/German", "description": "German Academic Exchange Service"},
            {"name": "Erasmus Mundus", "amount": "€25,000/year + tuition", "deadline": "January 15, 2025", "requirements": "Bachelor's degree", "description": "EU-funded scholarship"},
            {"name": "Turkish Government Scholarship", "amount": "Full tuition + stipend", "deadline": "February 20, 2025", "requirements": "Under 30 for Master's", "description": "Türkiye Bursları scholarship"},
        ]
    }
    
    # General international scholarships as default
    default_scholarships = [
        {"name": "Erasmus Mundus Joint Masters", "amount": "€25,000/year + tuition", "deadline": "January 15, 2025", "requirements": "Bachelor's degree, English proficiency", "description": "EU-funded scholarship for international students"},
        {"name": "Chevening Scholarship UK", "amount": "Full tuition + £1,200/month", "deadline": "November 7, 2025", "requirements": "2+ years work experience, leadership", "description": "UK government's global scholarship"},
        {"name": "DAAD Scholarship Germany", "amount": "€934/month + insurance", "deadline": "October 15, 2025", "requirements": "Good academic record", "description": "German Academic Exchange Service"},
        {"name": "Fulbright Foreign Student Program", "amount": "Full funding", "deadline": "February 1, 2025", "requirements": "Bachelor's degree, leadership", "description": "US government scholarship"},
        {"name": "Swiss Government Excellence Scholarship", "amount": "CHF 1,920/month", "deadline": "December 2024", "requirements": "Research proposal", "description": "For doctoral research in Switzerland"},
    ]
    
    return scholarships.get(country_lower, default_scholarships)
