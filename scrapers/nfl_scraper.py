"""
NFL Scraper - ESPN API no oficial + pro-football-reference scraping
Stats: DVOA proxy, ANY/A, EPA proxy, turnover diff, red zone, 3rd down
"""
import time
import requests
from datetime import date
from bs4 import BeautifulSoup

_cache = {}
CACHE_TTL = 3600

ESPN_NFL_BASE = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def _espn_get(endpoint: str, params: dict = None) -> dict | None:
    url = f'{ESPN_NFL_BASE}/{endpoint}'
    key = url + str(sorted((params or {}).items()))
    now = time.time()
    if key in _cache and now - _cache[key]['ts'] < CACHE_TTL:
        return _cache[key]['data']
    try:
        r = requests.get(url, params=params or {}, headers=HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
        _cache[key] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        print(f'[NFL] ESPN error {endpoint}: {e}')
        return None


def get_today_games() -> list[dict]:
    """Partidos NFL de hoy o proxima semana."""
    data = _espn_get('scoreboard')
    if not data:
        return []
    games = []
    try:
        for event in data.get('events', []):
            comp = event['competitions'][0]
            home = next(t for t in comp['competitors'] if t['homeAway'] == 'home')
            away = next(t for t in comp['competitors'] if t['homeAway'] == 'away')
            games.append({
                'game_id':   event['id'],
                'home_team': home['team']['displayName'],
                'away_team': away['team']['displayName'],
                'home_id':   home['team']['id'],
                'away_id':   away['team']['id'],
                'status':    event['status']['type']['description'],
                'venue':     comp.get('venue', {}).get('fullName', ''),
                'game_time': event.get('date', ''),
            })
    except Exception as e:
        print(f'[NFL] Parse games error: {e}')
    return games


def get_team_stats(team_id: str) -> dict:
    """Stats ofensivas y defensivas del equipo via ESPN."""
    data = _espn_get(f'teams/{team_id}/statistics')
    if not data:
        return _default_nfl_stats()
    try:
        stats = {}
        for cat in data.get('results', {}).get('stats', {}).get('categories', []):
            for s in cat.get('stats', []):
                stats[s['name']] = s.get('value', 0)

        pass_ypg  = float(stats.get('passingYardsPerGame', 230))
        rush_ypg  = float(stats.get('rushingYardsPerGame', 110))
        pts_pg    = float(stats.get('pointsPerGame', 22))
        pts_allow = float(stats.get('pointsAllowedPerGame', 22))
        to_diff   = float(stats.get('turnoverDifferential', 0))
        third_pct = float(stats.get('thirdDownPct', .380))
        rz_pct    = float(stats.get('redZonePct', .550))
        sacks     = float(stats.get('sacks', 20))

        # ANY/A proxy = (PassYds + 20*TD - 45*INT - Sack_Yds) / (Attempts + Sacks)
        # Usamos valores por partido como proxy
        any_a_proxy = (pass_ypg - 15) / 35  # normalizado

        # DVOA proxy = (pts_pg - pts_allow - 22) / 10
        dvoa_proxy = (pts_pg - pts_allow) / 10

        return {
            'pass_ypg': pass_ypg, 'rush_ypg': rush_ypg,
            'total_ypg': pass_ypg + rush_ypg,
            'pts_per_game': pts_pg, 'pts_allowed': pts_allow,
            'pt_diff': round(pts_pg - pts_allow, 2),
            'to_diff': to_diff,
            'third_down_pct': third_pct,
            'red_zone_pct': rz_pct,
            'sacks': sacks,
            'any_a_proxy': round(any_a_proxy, 3),
            'dvoa_proxy': round(dvoa_proxy, 3),
        }
    except Exception as e:
        print(f'[NFL] Team stats error: {e}')
        return _default_nfl_stats()


def _default_nfl_stats() -> dict:
    return {
        'pass_ypg': 230, 'rush_ypg': 110, 'total_ypg': 340,
        'pts_per_game': 22, 'pts_allowed': 22, 'pt_diff': 0,
        'to_diff': 0, 'third_down_pct': .380, 'red_zone_pct': .550,
        'sacks': 20, 'any_a_proxy': 0, 'dvoa_proxy': 0,
    }


def get_team_record(team_id: str) -> dict:
    """Record de temporada y ultimos 5 partidos."""
    data = _espn_get(f'teams/{team_id}')
    if not data:
        return {'wins': 0, 'losses': 0, 'ties': 0, 'win_pct': .500}
    try:
        record = data['team']['record']['items'][0]['stats']
        stats = {s['name']: s['value'] for s in record}
        w = int(stats.get('wins', 0))
        l = int(stats.get('losses', 0))
        t = int(stats.get('ties', 0))
        return {
            'wins': w, 'losses': l, 'ties': t,
            'win_pct': round(w / max(w+l+t, 1), 3),
            'streak': stats.get('streak', 0),
        }
    except Exception as e:
        print(f'[NFL] Record error: {e}')
        return {'wins': 0, 'losses': 0, 'ties': 0, 'win_pct': .500}
