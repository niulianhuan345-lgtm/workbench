#!/usr/bin/env python3
"""Fetch real-time weather from Open-Meteo for all cities in wx_daily.csv"""
import asyncio
import csv
import json
import httpx
from pypinyin import pinyin, Style

WMO_CODES = {
    0: '晴', 1: '晴', 2: '多云', 3: '阴',
    45: '雾', 48: '雾凇',
    51: '小毛毛雨', 53: '毛毛雨', 55: '大毛毛雨',
    56: '冻毛毛雨', 57: '大冻毛毛雨',
    61: '小雨', 63: '中雨', 65: '大雨',
    66: '冻雨', 67: '大冻雨',
    71: '小雪', 73: '中雪', 75: '大雪',
    77: '雪粒',
    80: '阵雨', 81: '中阵雨', 82: '大阵雨',
    85: '小阵雪', 86: '大阵雪',
    95: '雷暴', 96: '冰雹雷暴', 99: '大冰雹雷暴',
}

async def geocode(city_cn, client):
    py = ''.join([p[0] for p in pinyin(city_cn, style=Style.NORMAL)])
    try:
        resp = await client.get(
            'https://geocoding-api.open-meteo.com/v1/search',
            params={'name': py, 'count': 1, 'language': 'en', 'format': 'json'},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('results'):
                r = data['results'][0]
                return (r['latitude'], r['longitude'])
    except:
        pass
    return None

async def get_weather(lat, lon, client):
    try:
        resp = await client.get(
            'https://api.open-meteo.com/v1/forecast',
            params={'latitude': lat, 'longitude': lon, 'current_weather': 'true'},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            cw = data.get('current_weather', {})
            code = cw.get('weathercode', -1)
            return {
                'temp': cw.get('temperature', ''),
                'code': code,
                'wmo_text': WMO_CODES.get(code, '未知')
            }
    except:
        pass
    return None

async def process_city(city, client, semaphore):
    async with semaphore:
        coords = await geocode(city, client)
        if coords:
            weather = await get_weather(coords[0], coords[1], client)
            return (city, weather)
        return (city, None)

async def main():
    cities = []
    with open('wx_daily.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cities.append(row['城市'])
    
    print(f"Total cities: {len(cities)}")
    semaphore = asyncio.Semaphore(15)
    
    # Disable proxy by using a transport without proxies
    transport = httpx.AsyncHTTPTransport(retries=2)
    async with httpx.AsyncClient(transport=transport) as client:
        tasks = [process_city(city, client, semaphore) for city in cities]
        results = await asyncio.gather(*tasks)
    
    weather_map = {}
    success = 0
    for city, w in results:
        weather_map[city] = w
        if w:
            success += 1
    
    print(f"Fetched: {success}/{len(cities)}")
    
    with open('realtime_weather.json', 'w') as f:
        json.dump(weather_map, f, ensure_ascii=False, indent=2)
    
    # Write CSV for K column
    with open('wx_k.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        for city in cities:
            w = weather_map.get(city)
            text = f"{w['wmo_text']} {w['temp']}°C" if w else ''
            writer.writerow([text])
    
    # Show sample
    for city, w in list(weather_map.items())[:5]:
        if w:
            print(f"  {city}: {w['wmo_text']} {w['temp']}°C")
        else:
            print(f"  {city}: FAILED")

if __name__ == '__main__':
    asyncio.run(main())
