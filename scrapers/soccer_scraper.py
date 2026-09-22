"""
Soccer Scraper - ESPN API + FBRef scraping
Stats: xG, xGA, forma, H2H, Dixon-Coles strength
"""
import time
import requests
from datetime import date
from bs4 import BeautifulSoup

_cache = {}
CACHE_TTL = 1800

ESPN_SOC_BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

LEAGUE_SLUGS = {
    'epl':     'eng.1',
    'laliga':  'esp.1',
    'mls':     'usa.1',
    'ligamx':  'mex.1',
    'ucl':     'uefa.champions',
    'bundesliga': 'ger.1',
    'seriea':  'ita.1',
}


def _espn_get(league: str, endpoint: str, params: dict = None) -> dict | None:
    slug = LEAGUE_SLUGS.get(league, 'eng.1')
    url  = f'{ESPN_SOC_BASE}/{slug}/{endpoint}'
    key  = url + str(sorted((params or {}).items()))
    now  = time.time()
    if key in _cache and now - _cache[key]['ts'] < CACHE_TTL:
        return _cache[key]['data']
    try:
        r = requests.get(url, params=params or {}, headers=HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
        _cache[key] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        print(f'[Soccer] ESPN error {league}/{endpoint}: {e}')
        return None


def get_today_games(leagues: list = None) -> list[dict]:
    """Partidos de hoy en todas las ligas configuradas."""
    if leagues is None:
        leagues = ['epl', 'laliga', 'mls', 'ligamx', 'ucl']
    all_games = []
    for league in leagues:
        data = _espn_get(league, 'scoreboard')
        if not data:
            continue
        try:
            for event in data.get('events', []):
                comp = event['competitions'][0]
                home = next(t for t in comp['competitors'] if t['homeAway'] == 'home')
                away = next(t for t in comp['competitors'] if t['homeAway'] == 'away')
                all_games.append({
                    'game_id':   event['id'],
                    'league':    league,
                    'home_team': home['team']['displayName'],
                    'away_team': away['team']['displayName'],
                    'home_id':   home['team']['id'],
                    'away_id':   away['team']['id'],
                    'status':    event['status']['type']['description'],
                    'venue':     comp.get('venue', {}).get('fullName', ''),
                    'game_time': event.get('date', ''),
                })
        except Exception as e:
            print(f'[Soccer] Parse {league} error: {e}')
    return all_games


def get_team_stats(team_id: str, league: str = 'epl') -> dict:
    """Stats del equipo: forma, goles, xG proxy."""
    data = _espn_get(league, f'teams/{team_id}/statistics')
    if not data:
        return _default_soccer_stats()
    try:
        stats = {}
        for cat in data.get('results', {}).get('stats', {}).get('categories', []):
            for s in cat.get('stats', []):
                stats[s['name']] = float(s.get('value', 0))

        gf = stats.get('goals', 0)
        ga = stats.get('goalsAgainst', 0)
        gp = max(stats.get('gamesPlayed', 1), 1)
        shots_pg = stats.get('shotsPerGame', 12)
        sot_pg   = stats.get('shotsOnTargetPerGame', 4)
        poss     = stats.get('possessionPct', 50)

        # xG proxy: shots_on_target * 0.33 (conversion media)
        xg_pg  = round(sot_pg * 0.33, 2)
        xga_pg = round((ga / gp), 2)

        return {
            'goals_pg': round(gf / gp, 2),
            'goals_against_pg': round(ga / gp, 2),
            'xg_pg': xg_pg,
            'xga_pg': xga_pg,
            'shots_pg': shots_pg,
            'sot_pg': sot_pg,
            'possession': poss,
            'gd_pg': round((gf - ga) / gp, 2),
        }
    except Exception as e:
        print(f'[Soccer] Team stats error: {e}')
        return _default_soccer_stats()


def _default_soccer_stats() -> dict:
    return {
        'goals_pg': 1.3, 'goals_against_pg': 1.3,
        'xg_pg': 1.2, 'xga_pg': 1.2,
        'shots_pg': 12, 'sot_pg': 4,
        'possession': 50, 'gd_pg': 0,
    }


def compute_dixon_coles_strength(home_stats: dict, away_stats: dict,
                                  home_adv: float = 1.25) -> dict:
    """
    Calcula lambda_home y lambda_away usando stats de xG.
    Parametro rho tipicamente -0.1 (correlacion negativa en marcadores bajos).
    """
    lam_h = home_stats['xg_pg'] * (away_stats['xga_pg'] / 1.2) * home_adv
    lam_a = away_stats['xg_pg'] * (home_stats['xga_pg'] / 1.2)
    return {
        'lambda_home': round(max(lam_h, 0.3), 3),
        'lambda_away': round(max(lam_a, 0.3), 3),
        'rho': -0.1,
    }
