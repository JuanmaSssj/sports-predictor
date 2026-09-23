"""
ESPN Odds Scraper - Reemplaza a The Odds API.
Endpoint publico, gratuito, sin API key.
https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard
"""
import time
import requests
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from scrapers.espn_team_map import espn_to_mlb_id

_cache = {}
CACHE_TTL = 900  # 15 min

ESPN_BASE = 'https://site.api.espn.com/apis/site/v2/sports'
MEXICO_TZ = ZoneInfo('America/Mexico_City')

# Mapeo de sport -> (sport_espn, league_espn)
SPORT_KEYS = {
    'baseball': ('baseball', 'mlb'),
    'nba':      ('basketball', 'nba'),
    'nfl':      ('football', 'nfl'),
    'soccer':   ('soccer', 'eng.1'),  # Premier League por default
}


def _get(url: str) -> dict | None:
    now = time.time()
    if url in _cache and now - _cache[url]['ts'] < CACHE_TTL:
        return _cache[url]['data']
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        data = r.json()
        _cache[url] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        print(f'[ESPN] Error {url}: {e}')
        return None


def _extract_moneyline(odds_item: dict, side: str) -> int | None:
    """Extrae el moneyline de home o away. Devuelve int (ej. -126 o +105)."""
    try:
        ml = odds_item.get('moneyline', {})
        side_data = ml.get(side, {})
        close = side_data.get('close', {})
        odds_str = close.get('odds')
        if odds_str:
            return int(str(odds_str).replace('+', ''))
    except Exception:
        pass
    return None


def _parse_event(event: dict) -> dict | None:
    """Convierte un evento de ESPN en el formato interno."""
    try:
        comp = event.get('competitions', [{}])[0]
        odds_list = comp.get('odds', [])
        if not odds_list:
            return None

        o = odds_list[0]
        home_team = o.get('homeTeamOdds', {}).get('team', {})
        away_team = o.get('awayTeamOdds', {}).get('team', {})

        espn_home_id = str(home_team.get('id', ''))
        espn_away_id = str(away_team.get('id', ''))

        mlb_home_id = espn_to_mlb_id(espn_home_id)
        mlb_away_id = espn_to_mlb_id(espn_away_id)

        # Convertir UTC a hora de Mexico
        game_date_utc = event.get('date', '')
        try:
            dt_utc = datetime.fromisoformat(game_date_utc.replace('Z', '+00:00'))
            dt_mx = dt_utc.astimezone(MEXICO_TZ)
            time_mx = dt_mx.strftime('%d/%m %H:%M')
        except Exception:
            time_mx = game_date_utc

        return {
            'game_id':       event.get('id'),
            'home_team':     home_team.get('displayName', ''),
            'away_team':     away_team.get('displayName', ''),
            'home_id':       mlb_home_id,       # MLB Stats API ID
            'away_id':       mlb_away_id,       # MLB Stats API ID
            'espn_home_id':  espn_home_id,      # ESPN ID (para debug)
            'espn_away_id':  espn_away_id,      # ESPN ID (para debug)
            'ml_home':       _extract_moneyline(o, 'home'),
            'ml_away':       _extract_moneyline(o, 'away'),
            'total_line':    o.get('overUnder'),
            'spread_home':   o.get('spread'),
            'provider':      o.get('provider', {}).get('name', 'ESPN'),
            'game_time':     game_date_utc,
            'time_mx':       time_mx,
            'status':        event.get('status', {}).get('type', {}).get('description', 'Scheduled'),
            'sport':         'baseball',
        }
    except Exception as e:
        print(f'[ESPN] parse_event error: {e}')
        return None


def get_games_with_odds(sport: str) -> list[dict]:
    """Partidos del dia con odds. Espectáculo: baseball, nba, nfl, soccer."""
    if sport not in SPORT_KEYS:
        return []
    espn_sport, espn_league = SPORT_KEYS[sport]
    url = f'{ESPN_BASE}/{espn_sport}/{espn_league}/scoreboard'
    data = _get(url)
    if not data:
        return []

    games = []
    for event in data.get('events', []):
        parsed = _parse_event(event)
        if parsed and parsed.get('ml_home') and parsed.get('ml_away'):
            games.append(parsed)
    return games


def get_upcoming_games(sport: str, days: int = 3) -> list[dict]:
    """Partidos de los proximos N dias."""
    if sport not in SPORT_KEYS:
        return []
    espn_sport, espn_league = SPORT_KEYS[sport]
    all_games = []
    for i in range(days):
        d = (date.today() + timedelta(days=i)).strftime('%Y%m%d')
        url = f'{ESPN_BASE}/{espn_sport}/{espn_league}/scoreboard?dates={d}'
        data = _get(url)
        if not data:
            continue
        for event in data.get('events', []):
            parsed = _parse_event(event)
            if parsed:
                all_games.append(parsed)
    return all_games


def american_to_prob(american: int | None) -> float:
    """Convierte momio americano a probabilidad implicita."""
    if american is None:
        return 0.5
    try:
        american = float(american)
        if american > 0:
            return 100 / (american + 100)
        return abs(american) / (abs(american) + 100)
    except Exception:
        return 0.5