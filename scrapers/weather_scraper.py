"""
Weather Scraper - Open-Meteo API (100% gratuita, sin API key)
Impacto en totales: viento alto -> under, lluvia -> under, frio extremo -> under
"""
import requests
from config import OPEN_METEO_BASE

# Coordenadas aproximadas de estadios principales
STADIUM_COORDS = {
    # NFL
    'Kansas City Chiefs':    (39.0489, -94.4839),
    'Buffalo Bills':         (42.7738, -78.7870),
    'Dallas Cowboys':        (32.7473, -97.0945),
    'Green Bay Packers':     (44.5013, -88.0622),
    'Chicago Bears':         (41.8623, -87.6167),
    'New England Patriots':  (42.0909, -71.2643),
    'Las Vegas Raiders':     (36.0909, -115.1833),
    'Los Angeles Rams':      (33.9535, -118.3392),
    'San Francisco 49ers':   (37.4033, -121.9694),
    'Seattle Seahawks':      (47.5952, -122.3316),
    'Miami Dolphins':        (25.9580, -80.2389),
    'Tampa Bay Buccaneers':  (27.9759, -82.5033),
    # MLB
    'New York Yankees':      (40.8296, -73.9262),
    'Boston Red Sox':        (42.3467, -71.0972),
    'Chicago Cubs':          (41.9484, -87.6553),
    'Los Angeles Dodgers':   (34.0739, -118.2400),
    'San Francisco Giants':  (37.7786, -122.3893),
    'Houston Astros':        (29.7573, -95.3555),
    'Atlanta Braves':        (33.8908, -84.4678),
    'New York Mets':         (40.7571, -73.8458),
    # Default
    'DEFAULT':               (40.7128, -74.0060),
}


def get_weather(home_team: str, sport: str) -> dict:
    """
    Obtiene clima actual/pronostico para el estadio del equipo local.
    Solo relevante para deportes al aire libre: nfl, baseball, soccer.
    """
    if sport == 'nba':
        return {'indoor': True, 'impact': 'none', 'description': 'Juego en interior'}

    lat, lon = STADIUM_COORDS.get(home_team, STADIUM_COORDS['DEFAULT'])

    try:
        url = f'{OPEN_METEO_BASE}/forecast'
        params = {
            'latitude':   lat,
            'longitude':  lon,
            'current':    'temperature_2m,wind_speed_10m,precipitation,weathercode',
            'hourly':     'precipitation_probability',
            'forecast_days': 1,
            'wind_speed_unit': 'mph',
            'temperature_unit': 'fahrenheit',
        }
        r = requests.get(url, params=params, timeout=8)
        r.raise_for_status()
        data = r.json()

        current = data.get('current', {})
        temp_f      = current.get('temperature_2m', 72)
        wind_mph    = current.get('wind_speed_10m', 5)
        precip_mm   = current.get('precipitation', 0)
        wcode       = current.get('weathercode', 0)

        # Calcular impacto en totales
        under_lean = 0.0
        factors = []

        if wind_mph > 20:
            under_lean += 0.08
            factors.append(f'Viento fuerte {wind_mph:.0f}mph')
        elif wind_mph > 15:
            under_lean += 0.04
            factors.append(f'Viento moderado {wind_mph:.0f}mph')

        if precip_mm > 2 or wcode in (61, 63, 65, 71, 73, 75, 80, 81, 82):
            under_lean += 0.07
            factors.append('Lluvia/nieve')

        if temp_f < 35:
            under_lean += 0.06
            factors.append(f'Frio extremo {temp_f:.0f}F')
        elif temp_f < 45:
            under_lean += 0.03
            factors.append(f'Frio {temp_f:.0f}F')

        impact = 'UNDER' if under_lean >= 0.06 else ('leve_under' if under_lean > 0 else 'none')

        return {
            'indoor':       False,
            'temp_f':       round(temp_f, 1),
            'wind_mph':     round(wind_mph, 1),
            'precip_mm':    round(precip_mm, 2),
            'under_lean':   round(under_lean, 3),
            'impact':       impact,
            'factors':      factors,
            'description':  f'{temp_f:.0f}F, Viento {wind_mph:.0f}mph' + (' - ' + ', '.join(factors) if factors else ''),
        }

    except Exception as e:
        print(f'[WeatherScraper] Error: {e}')
        return {'indoor': False, 'impact': 'none', 'description': 'Clima no disponible',
                'temp_f': 72, 'wind_mph': 0, 'under_lean': 0}
