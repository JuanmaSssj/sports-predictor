"""
Odds Scraper - The-Odds-API
Solo se usa para dashboard principal y picks. NUNCA durante entrenamiento.
Cache de 30 minutos para conservar las 500 consultas mensuales.
"""
import time
import requests
from config import ODDS_API_KEY, ODDS_API_BASE

_cache = {}

SPORT_KEYS = {
    'soccer':               ['soccer_epl', 'soccer_usa_mls', 'soccer_spain_la_liga',
                             'soccer_mexico_ligamx', 'soccer_uefa_champs_league'],
    'baseball':             ['baseball_mlb'],
    'baseball_mlb':         ['baseball_mlb'],
    'nfl':                  ['americanfootball_nfl'],
    'americanfootball_nfl': ['americanfootball_nfl'],
    'nba':                  ['basketball_nba'],
    'basketball_nba':       ['basketball_nba'],
}


def _cached_get(url: str, params: dict, ttl: int = 1800) -> dict | None:
    key = url + str(sorted(params.items()))
    now = time.time()
    if key in _cache and now - _cache[key]['ts'] < ttl:
        return _cache[key]['data']
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        _cache[key] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        print(f'[OddsScraper] Error: {e}')
        return None


def get_games_with_odds(sport: str) -> list[dict]:
    """
    Retorna lista de partidos del dia con momios ML, spread y totales.
    sport: 'soccer' | 'baseball' | 'nfl' | 'nba'
    """
    sport_keys = SPORT_KEYS.get(sport, [])
    all_games = []

    for sport_key in sport_keys:
        url = f'{ODDS_API_BASE}/sports/{sport_key}/odds'
        params = {
            'apiKey':   ODDS_API_KEY,
            'regions':  'us',
            'markets':  'h2h,spreads,totals',
            'oddsFormat': 'american',
            'dateFormat': 'iso',
        }
        data = _cached_get(url, params)
        if not data:
            continue

        for game in data:
            parsed = _parse_game(game, sport_key)
            if parsed:
                all_games.append(parsed)

    # Ordenar por volumen de apuestas (usamos spread como proxy de liquidez)
    all_games.sort(key=lambda g: abs(g.get('spread_home', 0)))
    return all_games


def _parse_game(game: dict, sport_key: str) -> dict | None:
    try:
        bookmakers = game.get('bookmakers', [])
        if not bookmakers:
            return None

        # Usar el primer bookmaker disponible (Draftkings o Fanduel preferido)
        bm = next((b for b in bookmakers if b['key'] in ('draftkings', 'fanduel')),
                  bookmakers[0])

        ml_home = ml_away = ml_draw = None
        spread_home = spread_line = None
        total_line = None

        for market in bm.get('markets', []):
            if market['key'] == 'h2h':
                for outcome in market['outcomes']:
                    if outcome['name'] == game['home_team']:
                        ml_home = outcome['price']
                    elif outcome['name'] == game['away_team']:
                        ml_away = outcome['price']
                    elif outcome['name'] == 'Draw':
                        ml_draw = outcome['price']

            elif market['key'] == 'spreads':
                for outcome in market['outcomes']:
                    if outcome['name'] == game['home_team']:
                        spread_home = outcome['price']
                        spread_line = outcome.get('point', 0)

            elif market['key'] == 'totals':
                for outcome in market['outcomes']:
                    if outcome['name'] == 'Over':
                        total_line = outcome.get('point', 0)

        return {
            'id':          game['id'],
            'sport':       sport_key,
            'home_team':   game['home_team'],
            'away_team':   game['away_team'],
            'commence':    game['commence_time'],
            'ml_home':     ml_home,
            'ml_away':     ml_away,
            'ml_draw':     ml_draw,
            'spread_home': spread_home,
            'spread_line': spread_line,
            'total_line':  total_line,
        }
    except Exception as e:
        print(f'[OddsScraper] Parse error: {e}')
        return None


def american_to_prob(american: int | None) -> float:
    """Convierte momio americano a probabilidad implicita (sin overround)."""
    if american is None:
        return 0.0
    if american > 0:
        return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)
