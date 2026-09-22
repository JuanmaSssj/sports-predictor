"""
MLB Scraper - MLB Stats API oficial (100% gratuita, sin API key)
https://statsapi.mlb.com/api/v1
Incluye: pitchers, batters, bullpen, splits, sabermetricas
"""
import time
import requests
from datetime import date
from config import MLB_API_BASE

_cache = {}
CACHE_TTL = 1800


def _get(endpoint: str, params: dict = None) -> dict | list | None:
    url = f'{MLB_API_BASE}{endpoint}'
    key = url + str(sorted((params or {}).items()))
    now = time.time()
    if key in _cache and now - _cache[key]['ts'] < CACHE_TTL:
        return _cache[key]['data']
    try:
        r = requests.get(url, params=params or {}, timeout=12)
        r.raise_for_status()
        data = r.json()
        _cache[key] = {'data': data, 'ts': now}
        return data
    except Exception as e:
        print(f'[MLB] Error {endpoint}: {e}')
        return None


def get_today_games() -> list[dict]:
    """Partidos MLB de hoy con equipos y probable pitchers."""
    today = date.today().strftime('%Y-%m-%d')
    data = _get('/schedule', {'sportId': 1, 'date': today,
                              'hydrate': 'probablePitcher,team,linescore'})
    if not data:
        return []

    games = []
    for date_entry in data.get('dates', []):
        for g in date_entry.get('games', []):
            home = g['teams']['home']
            away = g['teams']['away']
            game = {
                'game_id':    g['gamePk'],
                'status':     g['status']['detailedState'],
                'home_team':  home['team']['name'],
                'away_team':  away['team']['name'],
                'home_id':    home['team']['id'],
                'away_id':    away['team']['id'],
                'venue':      g.get('venue', {}).get('name', ''),
                'game_time':  g.get('gameDate', ''),
                'home_pitcher': _extract_pitcher(home),
                'away_pitcher': _extract_pitcher(away),
            }
            games.append(game)
    return games


def _extract_pitcher(team_data: dict) -> dict:
    p = team_data.get('probablePitcher', {})
    if not p:
        return {'name': 'TBD', 'id': None}
    return {'name': p.get('fullName', 'TBD'), 'id': p.get('id')}


def get_pitcher_stats(pitcher_id: int) -> dict:
    """Stats completas del pitcher: ERA, WHIP, FIP, K/9, BB/9, HR/9."""
    if not pitcher_id:
        return {}
    data = _get(f'/people/{pitcher_id}/stats',
                {'stats': 'season', 'group': 'pitching', 'season': date.today().year})
    if not data:
        return {}
    try:
        splits = data['stats'][0]['splits']
        if not splits:
            return {}
        s = splits[0]['stat']
        ip   = float(s.get('inningsPitched', 1) or 1)
        era  = float(s.get('era', 4.50) or 4.50)
        whip = float(s.get('whip', 1.30) or 1.30)
        k9   = float(s.get('strikeoutsPer9Inn', 8.0) or 8.0)
        bb9  = float(s.get('walksPer9Inn', 3.0) or 3.0)
        hr   = int(s.get('homeRunsAllowed', 0) or 0)
        bb   = int(s.get('baseOnBalls', 0) or 0)
        hbp  = int(s.get('hitBatsmen', 0) or 0)
        k    = int(s.get('strikeOuts', 0) or 0)
        # FIP = (13*HR + 3*(BB+HBP) - 2*K) / IP + cFIP
        # cFIP constante de liga ~3.10 para MLB moderna
        fip  = (13*hr + 3*(bb+hbp) - 2*k) / max(ip, 1) + 3.10
        return {
            'era': era, 'whip': whip, 'k9': k9, 'bb9': bb9,
            'fip': round(fip, 2),
            'hr9': round(hr / max(ip, 1) * 9, 2),
            'k_bb': round(k9 / max(bb9, 0.1), 2),
            'games': int(s.get('gamesStarted', 0) or 0),
            'ip': ip,
            'wins': int(s.get('wins', 0) or 0),
            'losses': int(s.get('losses', 0) or 0),
        }
    except Exception as e:
        print(f'[MLB] Pitcher stats error: {e}')
        return {}


def get_team_batting_stats(team_id: int) -> dict:
    """Stats de bateo del equipo: AVG, OBP, SLG, OPS, wOBA proxy."""
    data = _get(f'/teams/{team_id}/stats',
                {'stats': 'season', 'group': 'hitting', 'season': date.today().year})
    if not data:
        return {}
    try:
        splits = data['stats'][0]['splits']
        if not splits:
            return {}
        s = splits[0]['stat']
        avg  = float(s.get('avg', .250) or .250)
        obp  = float(s.get('obp', .320) or .320)
        slg  = float(s.get('slg', .400) or .400)
        ops  = obp + slg
        # wOBA proxy: 0.72*BB + 0.75*HBP + 0.90*1B + 1.24*2B + 1.56*3B + 1.95*HR / PA
        bb   = int(s.get('baseOnBalls', 0) or 0)
        h    = int(s.get('hits', 0) or 0)
        hr   = int(s.get('homeRuns', 0) or 0)
        doubles = int(s.get('doubles', 0) or 0)
        triples = int(s.get('triples', 0) or 0)
        singles = h - doubles - triples - hr
        pa   = int(s.get('plateAppearances', 1) or 1)
        woba = (0.72*bb + 0.90*singles + 1.24*doubles + 1.56*triples + 1.95*hr) / max(pa, 1)
        # BABIP = (H - HR) / (AB - K - HR + SF)
        ab   = int(s.get('atBats', 1) or 1)
        k    = int(s.get('strikeOuts', 0) or 0)
        sf   = int(s.get('sacFlies', 0) or 0)
        babip = (h - hr) / max(ab - k - hr + sf, 1)
        iso  = slg - avg
        return {
            'avg': avg, 'obp': obp, 'slg': slg, 'ops': round(ops, 3),
            'woba': round(woba, 3), 'babip': round(babip, 3),
            'iso': round(iso, 3),
            'k_pct': round(k / max(pa, 1), 3),
            'bb_pct': round(bb / max(pa, 1), 3),
            'runs_per_game': round(int(s.get('runs', 0) or 0) / max(int(s.get('gamesPlayed', 1) or 1), 1), 2),
        }
    except Exception as e:
        print(f'[MLB] Batting stats error: {e}')
        return {}


def get_team_last_n(team_id: int, n: int = 10) -> dict:
    """Record de los ultimos N partidos y racha actual."""
    data = _get(f'/teams/{team_id}/records',
                {'leagueId': '103,104', 'season': date.today().year})
    # Fallback: usar standings
    standings = _get('/standings',
                     {'leagueId': '103,104', 'season': date.today().year,
                      'hydrate': 'team,record'})
    if not standings:
        return {'wins': 0, 'losses': 0, 'win_pct': .500}
    try:
        for record in standings.get('records', []):
            for tr in record.get('teamRecords', []):
                if tr['team']['id'] == team_id:
                    w = tr['wins']
                    l = tr['losses']
                    last10 = tr.get('records', {}).get('splitRecords', [])
                    l10_w = l10_l = 0
                    for split in last10:
                        if split.get('type') == 'lastTen':
                            l10_w = split['wins']
                            l10_l = split['losses']
                    return {
                        'wins': w, 'losses': l,
                        'win_pct': round(w / max(w+l, 1), 3),
                        'last10_wins': l10_w,
                        'last10_losses': l10_l,
                        'last10_pct': round(l10_w / max(l10_w+l10_l, 1), 3),
                        'streak': tr.get('streak', {}).get('streakCode', 'W1'),
                    }
    except Exception as e:
        print(f'[MLB] Last N error: {e}')
    return {'wins': 0, 'losses': 0, 'win_pct': .500}


def get_full_game_data(game: dict) -> dict:
    """Enriquece un partido con todas las stats disponibles."""
    home_id = game['home_id']
    away_id = game['away_id']
    home_p  = game['home_pitcher']['id']
    away_p  = game['away_pitcher']['id']

    return {
        **game,
        'home_batting':  get_team_batting_stats(home_id),
        'away_batting':  get_team_batting_stats(away_id),
        'home_pitcher_stats': get_pitcher_stats(home_p),
        'away_pitcher_stats': get_pitcher_stats(away_p),
        'home_record':   get_team_last_n(home_id),
        'away_record':   get_team_last_n(away_id),
    }
