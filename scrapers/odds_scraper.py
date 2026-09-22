"""
Odds Scraper - The-Odds-API
Solo para dashboard y picks. NUNCA durante entrenamiento.
Cache 30 min. Timezone: America/Mexico_City
"""
import time
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from config import ODDS_API_KEY, ODDS_API_BASE

_cache = {}
MEXICO_TZ = ZoneInfo('America/Mexico_City')

SPORT_KEYS = {
    'soccer': [
        'soccer_mexico_ligamx',
        'soccer_epl',
        'soccer_spain_la_liga',
        'soccer_germany_bundesliga',
        'soccer_italy_serie_a',
        'soccer_france_ligue_one',
        'soccer_uefa_champs_league',
        'soccer_uefa_europa_league',
        'soccer_usa_mls',
    ],
    'baseball': [
        'baseball_mlb',
        'baseball_kbo',
        'baseball_npb',
    ],
    'nfl': [
        'americanfootball_nfl',
        'americanfootball_ncaaf',
    ],
    'nba': [
        'basketball_nba',
        'basketball_wnba',
        'basketball_nbl',
    ],
}


def _now_mexico():
    return datetime.now(MEXICO_TZ)


def _today_range_utc():
    now_mx   = _now_mexico()
    start_mx = now_mx.replace(hour=0,  minute=0,  second=0,  microsecond=0)
    end_mx   = now_mx.replace(hour=23, minute=59, second=59, microsecond=0)
    utc      = timezone.utc
    return start_mx.astimezone(utc), end_mx.astimezone(utc)


def _cached_get(url, params, ttl=1800):
    key = url + str(sorted(params.items()))
    now = time.time()
    if key in _cache and now - _cache[key]['ts'] < ttl:
        return _cache[key]['data']
    try:
        r = requests.get(url, params=params, timeout=12)
        r.raise_for_status()
        data = r.json()
        _cache[key] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        print(f'[OddsScraper] Error: {e}')
        return None


def get_games_with_odds(sport: str, days_ahead: int = 0) -> list:
    sport_keys = SPORT_KEYS.get(sport, [])
    all_games  = []
    start_utc, end_utc = _today_range_utc()

    if days_ahead > 0:
        start_utc += timedelta(days=days_ahead)
        end_utc   += timedelta(days=days_ahead)

    for sport_key in sport_keys:
        url = f'{ODDS_API_BASE}/sports/{sport_key}/odds'
        params = {
            'apiKey':     ODDS_API_KEY,
            'regions':    'us',
            'markets':    'h2h,spreads,totals',
            'oddsFormat': 'american',
            'dateFormat': 'iso',
            'commenceTimeFrom': start_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'commenceTimeTo':   end_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
        }
        data = _cached_get(url, params)
        if not data:
            continue
        for game in data:
            parsed = _parse_game(game, sport_key)
            if parsed:
                all_games.append(parsed)

    all_games.sort(key=lambda g: g.get('commence', ''))
    return all_games


def get_upcoming_games(sport: str, days: int = 3) -> list:
    all_games = []
    for d in range(1, days + 1):
        games = get_games_with_odds(sport, days_ahead=d)
        for g in games:
            g['days_ahead'] = d
        all_games.extend(games)
    return all_games


def _parse_game(game: dict, sport_key: str):
    try:
        bookmakers = game.get('bookmakers', [])
        if not bookmakers:
            return None
        bm = next((b for b in bookmakers
                   if b['key'] in ('draftkings', 'fanduel', 'betmgm')),
                  bookmakers[0])

        ml_home = ml_away = ml_draw = None
        spread_home = spread_line = None
        total_line  = None

        for market in bm.get('markets', []):
            if market['key'] == 'h2h':
                for o in market['outcomes']:
                    if o['name'] == game['home_team']:   ml_home = o['price']
                    elif o['name'] == game['away_team']: ml_away = o['price']
                    elif o['name'] == 'Draw':            ml_draw = o['price']
            elif market['key'] == 'spreads':
                for o in market['outcomes']:
                    if o['name'] == game['home_team']:
                        spread_home = o['price']
                        spread_line = o.get('point', 0)
            elif market['key'] == 'totals':
                for o in market['outcomes']:
                    if o['name'] == 'Over':
                        total_line = o.get('point', 0)

        commence_utc = datetime.fromisoformat(
            game['commence_time'].replace('Z', '+00:00'))
        commence_mx  = commence_utc.astimezone(MEXICO_TZ)
        time_mx_str  = commence_mx.strftime('%d/%m %I:%M %p CT')

        return {
            'id':          game['id'],
            'sport':       sport_key,
            'home_team':   game['home_team'],
            'away_team':   game['away_team'],
            'commence':    game['commence_time'],
            'time_mx':     time_mx_str,
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


def american_to_prob(american):
    if american is None: return 0.0
    if american > 0: return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)
