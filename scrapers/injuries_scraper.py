"""
Injuries Scraper - ESPN injury reports (sin API key, scraping publico)
Impacto: Out=-1.0, Doubtful=-0.7, Questionable=-0.4, Probable=-0.1
"""
import time
import requests
from bs4 import BeautifulSoup

_cache = {}
CACHE_TTL = 3600  # 1 hora

ESPN_INJURY_URLS = {
    'nfl':      'https://www.espn.com/nfl/injuries',
    'nba':      'https://www.espn.com/nba/injuries',
    'baseball': 'https://www.espn.com/mlb/injuries',
    'soccer':   'https://www.espn.com/soccer/injuries',
}

IMPACT_MAP = {
    'out':          -1.0,
    'doubtful':     -0.7,
    'questionable': -0.4,
    'probable':     -0.1,
    'day-to-day':   -0.3,
    'ir':           -1.0,
    'suspended':    -1.0,
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36'
}


def get_injuries(sport: str) -> dict[str, list]:
    """
    Retorna dict {team_name: [{'player', 'status', 'injury', 'impact'}]}
    """
    now = time.time()
    if sport in _cache and now - _cache[sport]['ts'] < CACHE_TTL:
        return _cache[sport]['data']

    url = ESPN_INJURY_URLS.get(sport)
    if not url:
        return {}

    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'lxml')
        result = _parse_espn_injuries(soup)
        _cache[sport] = {'data': result, 'ts': now}
        return result
    except Exception as e:
        print(f'[InjuriesScraper] Error {sport}: {e}')
        return {}


def _parse_espn_injuries(soup: BeautifulSoup) -> dict:
    result = {}
    # ESPN estructura: tabla por equipo con filas de jugadores
    tables = soup.find_all('div', class_='Table__Scroller')
    team_headers = soup.find_all('div', class_='injuries__teamName')

    for i, table in enumerate(tables):
        team_name = ''
        if i < len(team_headers):
            team_name = team_headers[i].get_text(strip=True)

        players = []
        rows = table.find_all('tr', class_='Table__TR')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 3:
                continue
            player  = cols[0].get_text(strip=True)
            pos     = cols[1].get_text(strip=True) if len(cols) > 1 else ''
            status  = cols[2].get_text(strip=True).lower() if len(cols) > 2 else ''
            injury  = cols[3].get_text(strip=True) if len(cols) > 3 else ''
            impact  = IMPACT_MAP.get(status, -0.2)
            if player:
                players.append({
                    'player': player,
                    'position': pos,
                    'status': status,
                    'injury': injury,
                    'impact': impact,
                })

        if team_name and players:
            result[team_name] = players

    return result


def get_team_injury_impact(team: str, sport: str) -> dict:
    """
    Calcula impacto total de lesiones para un equipo.
    Retorna: {'total_impact': float, 'key_players_out': list, 'summary': str}
    """
    all_injuries = get_injuries(sport)
    team_injuries = all_injuries.get(team, [])

    total_impact = sum(p['impact'] for p in team_injuries)
    key_out = [p for p in team_injuries if p['impact'] <= -0.7]

    summary = 'Sin lesiones significativas'
    if key_out:
        names = ', '.join(p['player'] for p in key_out[:3])
        summary = f'Bajas importantes: {names}'
    elif team_injuries:
        summary = f'{len(team_injuries)} jugador(es) en reporte'

    return {
        'total_impact': round(total_impact, 2),
        'key_players_out': key_out,
        'all_injuries': team_injuries,
        'summary': summary,
    }
