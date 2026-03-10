import urllib.request
import urllib.parse
import ssl
import os
import json

import json

def get_my_location() -> str:
    """Gets the user's current physical location (city, region, country) based on their public IP address. Use this when you need to know where the user is."""
    try:
        url = "http://ip-api.com/json/?lang=zh-CN"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        # Build proxy handler if environment variables are set
        proxies = {}
        if os.environ.get("HTTP_PROXY"):
            proxies["http"] = os.environ.get("HTTP_PROXY")
        if os.environ.get("HTTPS_PROXY"):
            proxies["https"] = os.environ.get("HTTPS_PROXY")
            
        proxy_support = urllib.request.ProxyHandler(proxies)
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        opener = urllib.request.build_opener(proxy_support, urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        if data.get("status") == "success":
            return f"当前位置: {data.get('country')} {data.get('regionName')} {data.get('city')}"
        else:
            return "无法获取位置信息。"
            
    except Exception as e:
        return f"获取位置信息失败: {str(e)}"

def get_weather(city: str) -> str:
    """Gets the current weather for a specified city."""
    try:
        # Get coordinates for the city using Open-Meteo Geocoding API
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1&language=zh"
        req = urllib.request.Request(geocode_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        # Build proxy handler if environment variables are set
        proxies = {}
        if os.environ.get("HTTP_PROXY"):
            proxies["http"] = os.environ.get("HTTP_PROXY")
        if os.environ.get("HTTPS_PROXY"):
            proxies["https"] = os.environ.get("HTTPS_PROXY")
            
        proxy_support = urllib.request.ProxyHandler(proxies)
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        opener = urllib.request.build_opener(proxy_support, urllib.request.HTTPSHandler(context=ctx))
        urllib.request.install_opener(opener)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        if not data.get("results"):
            return f"找不到城市 '{city}' 的坐标位置。"
            
        location = data["results"][0]
        lat = location["latitude"]
        lon = location["longitude"]
        name = location.get("name", city)
        
        # Get weather data using coordinates
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&timezone=auto"
        req2 = urllib.request.Request(weather_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req2, timeout=10) as response2:
            weather_data = json.loads(response2.read().decode('utf-8'))
            
        current = weather_data.get("current", {})
        temp = current.get("temperature_2m", "N/A")
        feels_like = current.get("apparent_temperature", "N/A")
        humidity = current.get("relative_humidity_2m", "N/A")
        wind_speed = current.get("wind_speed_10m", "N/A")
        
        code = current.get("weather_code", 0)
        weather_desc = "晴或多云" if code <= 3 else "雾" if code in (45, 48) else "雨" if code in (51,53,55,56,57,61,63,65,66,67,80,81,82) else "雪" if code in (71,73,75,77,85,86) else "雷阵雨" if code >= 95 else "未知"

        result = f"{name} 当前天气: {weather_desc}, 气温 {temp}°C (体感 {feels_like}°C), 湿度 {humidity}%, 风速 {wind_speed}km/h"
        return result
        
    except Exception as e:
        return f"获取天气信息失败 (Error fetching weather for {city}): {str(e)}。建议检查网络连接。"
