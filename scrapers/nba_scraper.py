"""
NBA Scraper - nba_api (libreria Python oficial de la comunidad)
Stats: ORtg, DRtg, NetRtg, Pace, eFG%, Four Factors, back-to-back
"""
import time
import requests
from datetime import date, timedelta

_cache = {}
CACHE_TTL = 1800

NBA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.nba.com/',
    'Accept': 'application/json',
    'x-nba-stats-origin': 'stats',
    'x-nba-stats-token': 'true',
}
NBA_BASE = 'https://stats.nba.com/stats'


def _nba_get(endpoint: str, params: dict) -> dict | None:
    key = endpoint + str(sorted(params.items()))
    now = time.time()
    if key in _cache and now - _cache[key]['ts'] < CACHE_TTL:
        return _cache[key]['data']
    try:
        r = requests.get(f'{NBA_BASE}/{endpoint}', headers=NBA_HEADERS,
                         params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        _cache[key] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        print(f'[NBA] Error {endpoint}: {e}')
        return None


def get_today_games() -> list[dict]:
    """Partidos NBA de hoy via scoreboard."""
    today = date.today().strftime('%m/%d/%Y')
    data = _nba_get('scoreboardv2', {
        'GameDate': today, 'LeagueID': '00', 'DayOffset': '0'
    })
    if not data:
        return []
    games = []
    try:
        sets = {rs['name']: rs for rs in data['resultSets']}
        game_header = sets.get('GameHeader', {})
        headers = game_header.get('headers', [])
        rows    = game_header.get('rowSet', [])
        idx = {h: i for i, h in enumerate(headers)}
        for row in rows:
            games.append({
                'game_id':   row[idx['GAME_ID']],
                'home_team': row[idx['HOME_TEAM_ID']],
                'away_team': row[idx['VISITOR_TEAM_ID']],
                'status':    row[idx['GAME_STATUS_TEXT']],
                'arena':     row[idx.get('ARENA_NAME', 0)] if 'ARENA_NAME' in idx else '',
            })
    except Exception as e:
        print(f'[NBA] Parse games error: {e}')
    return games


def get_team_advanced_stats(team_id: int, season: str = None) -> dict:
    """ORtg, DRtg, NetRtg, Pace, eFG%, TOV%, ORB%, FT/FGA (Four Factors)."""
    if not season:
        yr = date.today().year
        season = f'{yr-1}-{str(yr)[2:]}' if date.today().month < 10 else f'{yr}-{str(yr+1)[2:]}'
    data = _nba_get('teamdashboardbygeneralsplits', {
        'TeamID': team_id, 'Season': season, 'SeasonType': 'Regular Season',
        'MeasureType': 'Advanced', 'PerMode': 'PerGame',
        'PlusMinus': 'N', 'PaceAdjust': 'N', 'Rank': 'N',
        'Outcome': '', 'Location': '', 'Month': '0',
        'SeasonSegment': '', 'DateFrom': '', 'DateTo': '',
        'OpponentTeamID': '0', 'VsConference': '', 'VsDivision': '',
        'GameSegment': '', 'Period': '0', 'LastNGames': '0',
    })
    if not data:
        return _default_nba_stats()
    try:
        rs = data['resultSets'][0]
        headers = rs['headers']
        row = rs['rowSet'][0] if rs['rowSet'] else None
        if not row:
            return _default_nba_stats()
        d = dict(zip(headers, row))
        ortg = float(d.get('OFF_RATING', 110))
        drtg = float(d.get('DEF_RATING', 110))
        pace = float(d.get('PACE', 100))
        efg  = float(d.get('EFG_PCT', .500))
        tov  = float(d.get('TM_TOV_PCT', .140))
        orb  = float(d.get('OREB_PCT', .250))
        ftr  = float(d.get('FTA_RATE', .250))
        ts   = float(d.get('TS_PCT', .550))
        return {
            'ortg': ortg, 'drtg': drtg, 'net_rtg': round(ortg - drtg, 2),
            'pace': pace, 'efg_pct': efg, 'tov_pct': tov,
            'orb_pct': orb, 'ft_rate': ftr, 'ts_pct': ts,
            # Four Factors score (ponderado)
            'four_factors': round(0.4*efg - 0.25*tov + 0.20*orb + 0.15*ftr, 4),
        }
    except Exception as e:
        print(f'[NBA] Advanced stats error: {e}')
        return _default_nba_stats()


def _default_nba_stats() -> dict:
    return {'ortg': 110, 'drtg': 110, 'net_rtg': 0, 'pace': 100,
            'efg_pct': .500, 'tov_pct': .140, 'orb_pct': .250,
            'ft_rate': .250, 'ts_pct': .550, 'four_factors': 0}


def get_team_last10(team_id: int, season: str = None) -> dict:
    """Record ultimos 10 partidos y racha."""
    if not season:
        yr = date.today().year
        season = f'{yr-1}-{str(yr)[2:]}' if date.today().month < 10 else f'{yr}-{str(yr+1)[2:]}'
    data = _nba_get('teamdashboardbygeneralsplits', {
        'TeamID': team_id, 'Season': season, 'SeasonType': 'Regular Season',
        'MeasureType': 'Base', 'PerMode': 'PerGame',
        'PlusMinus': 'N', 'PaceAdjust': 'N', 'Rank': 'N',
        'LastNGames': '10',
        'Outcome': '', 'Location': '', 'Month': '0',
        'SeasonSegment': '', 'DateFrom': '', 'DateTo': '',
        'OpponentTeamID': '0', 'VsConference': '', 'VsDivision': '',
        'GameSegment': '', 'Period': '0',
    })
    if not data:
        return {'l10_wins': 5, 'l10_losses': 5, 'l10_pct': .500}
    try:
        rs = data['resultSets'][0]
        headers = rs['headers']
        row = rs['rowSet'][0] if rs['rowSet'] else None
        if not row:
            return {'l10_wins': 5, 'l10_losses': 5, 'l10_pct': .500}
        d = dict(zip(headers, row))
        w = int(d.get('W', 5))
        l = int(d.get('L', 5))
        return {'l10_wins': w, 'l10_losses': l, 'l10_pct': round(w/max(w+l,1), 3)}
    except:
        return {'l10_wins': 5, 'l10_losses': 5, 'l10_pct': .500}


def is_back_to_back(team_id: int) -> bool:
    """Detecta si el equipo jugo ayer (back-to-back)."""
    yesterday = (date.today() - timedelta(days=1)).strftime('%m/%d/%Y')
    data = _nba_get('scoreboardv2', {
        'GameDate': yesterday, 'LeagueID': '00', 'DayOffset': '0'
    })
    if not data:
        return False
    try:
        sets = {rs['name']: rs for rs in data['resultSets']}
        gh = sets.get('GameHeader', {})
        headers = gh.get('headers', [])
        rows    = gh.get('rowSet', [])
        idx = {h: i for i, h in enumerate(headers)}
        for row in rows:
            if (row[idx['HOME_TEAM_ID']] == team_id or
                    row[idx['VISITOR_TEAM_ID']] == team_id):
                return True
    except:
        pass
    return False
