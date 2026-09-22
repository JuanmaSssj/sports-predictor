"""
Auto-Trainer: analiza partidos de HOY y PROXIMOS, predice, verifica resultados.
NO usa Odds API. Solo APIs gratuitas.
NO analiza partidos que ya pasaron.
"""
import json
import time
import threading
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

MEXICO_TZ    = ZoneInfo('America/Mexico_City')
HISTORY_FILE = Path('data/training_history.json')


class AutoTrainer:
    def __init__(self):
        self.is_running     = False
        self._thread        = None
        self.history        = self._load_history()
        self.current_status = 'Inactivo'
        self.current_game   = ''

    # ---- Propiedades ----
    @property
    def total_analyzed(self): return len(self.history)

    @property
    def total_correct(self): return sum(1 for h in self.history if h.get('correct') is True)

    @property
    def win_rate(self):
        resolved = [h for h in self.history if h.get('correct') is not None]
        if not resolved: return 0.0
        return round(sum(1 for h in resolved if h['correct']) / len(resolved) * 100, 1)

    @property
    def last_10(self):
        resolved = [h for h in self.history if h.get('correct') is not None]
        return [('W' if h['correct'] else 'L') for h in resolved[-10:]]

    # ---- Control ----
    def start(self):
        if self.is_running: return
        self.is_running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        self.current_status = 'Detenido'
        self.current_game   = ''

    def get_status(self) -> dict:
        return {
            'is_running':     self.is_running,
            'status':         self.current_status,
            'current_game':   self.current_game,
            'total_analyzed': self.total_analyzed,
            'total_correct':  self.total_correct,
            'win_rate':       self.win_rate,
            'last_10':        self.last_10,
        }

    def get_history(self) -> list:
        """Retorna historial ordenado: pendientes primero, luego resueltos recientes."""
        pending  = [h for h in self.history if h.get('correct') is None]
        resolved = [h for h in self.history if h.get('correct') is not None]
        resolved_sorted = sorted(resolved, key=lambda x: x.get('timestamp',''), reverse=True)
        return (pending + resolved_sorted)[:50]

    # ---- Loop principal ----
    def _loop(self):
        while self.is_running:
            try:
                self.current_status = 'Buscando partidos de hoy y proximos...'
                self._analyze_all_sports()
                self._verify_past_predictions()
                self.current_status = 'Esperando siguiente ciclo (30 min)...'
                self.current_game   = ''
                for _ in range(180):  # 30 min en pasos de 10s
                    if not self.is_running: break
                    time.sleep(10)
            except Exception as e:
                print(f'[Trainer] Loop error: {e}')
                time.sleep(60)

    def _is_future_or_today(self, game_time_str: str) -> bool:
        """Verifica que el partido sea de hoy o futuro (hora Mexico)."""
        if not game_time_str:
            return True
        try:
            # Parsear ISO o string de fecha
            if 'T' in game_time_str:
                dt = datetime.fromisoformat(game_time_str.replace('Z', '+00:00'))
            else:
                return True  # si no hay fecha clara, incluir
            now_utc = datetime.now(timezone.utc)
            # Solo partidos que empiezan en las proximas 48h o que empezaron hace menos de 4h
            diff = (dt - now_utc).total_seconds()
            return diff > -14400  # no mas de 4 horas en el pasado
        except:
            return True

    def _analyze_all_sports(self):
        sports = [
            ('MLB',    self._analyze_mlb),
            ('NBA',    self._analyze_nba),
            ('NFL',    self._analyze_nfl),
            ('Soccer', self._analyze_soccer),
        ]
        for name, fn in sports:
            if not self.is_running: break
            try:
                self.current_status = f'Analizando {name}...'
                fn()
            except Exception as e:
                print(f'[Trainer] {name} error: {e}')

    def _analyze_mlb(self):
        try:
            from scrapers.mlb_scraper import get_today_games, get_full_game_data
            from models.sabermetrics import mlb_game_score
            games = get_today_games()
            for g in games[:5]:
                if not self.is_running: break
                gid = str(g['game_id'])
                if self._already_predicted(gid): continue
                if not self._is_future_or_today(g.get('game_time', '')):
                    continue
                self.current_game = f"MLB: {g['away_team']} @ {g['home_team']}"
                full  = get_full_game_data(g)
                score = mlb_game_score(
                    full.get('home_batting', {}), full.get('away_batting', {}),
                    full.get('home_pitcher_stats', {}), full.get('away_pitcher_stats', {}),
                )
                pred = 'HOME' if score['prob_home'] > 0.5 else 'AWAY'
                self._save_prediction({
                    'game_id':    gid,
                    'sport':      'MLB',
                    'game':       f"{g['away_team']} @ {g['home_team']}",
                    'home_team':  g['home_team'],
                    'away_team':  g['away_team'],
                    'prediction': pred,
                    'pick_name':  g['home_team'] if pred == 'HOME' else g['away_team'],
                    'prob':       round(score['prob_home'] if pred == 'HOME' else score['prob_away'], 3),
                    'home_pitcher': g.get('home_pitcher', {}).get('name', 'TBD'),
                    'away_pitcher': g.get('away_pitcher', {}).get('name', 'TBD'),
                    'game_time':  g.get('game_time', ''),
                    'timestamp':  datetime.now(timezone.utc).isoformat(),
                    'correct':    None,
                    'actual':     None,
                })
        except Exception as e:
            print(f'[Trainer] MLB analyze error: {e}')

    def _analyze_nba(self):
        try:
            from scrapers.nba_scraper import get_today_games, get_team_advanced_stats, is_back_to_back
            from models.sabermetrics import nba_win_probability
            games = get_today_games()
            for g in games[:5]:
                if not self.is_running: break
                gid = str(g['game_id'])
                if self._already_predicted(gid): continue
                self.current_game = f"NBA: {g['away_team']} @ {g['home_team']}"
                h = get_team_advanced_stats(g['home_team']) if g['home_team'] else {}
                a = get_team_advanced_stats(g['away_team']) if g['away_team'] else {}
                r = nba_win_probability(h, a,
                    is_back_to_back(g['home_team']) if g['home_team'] else False,
                    is_back_to_back(g['away_team']) if g['away_team'] else False)
                pred = 'HOME' if r['prob_home'] > 0.5 else 'AWAY'
                self._save_prediction({
                    'game_id':    gid,
                    'sport':      'NBA',
                    'game':       f"{g['away_team']} @ {g['home_team']}",
                    'home_team':  str(g['home_team']),
                    'away_team':  str(g['away_team']),
                    'prediction': pred,
                    'pick_name':  str(g['home_team']) if pred == 'HOME' else str(g['away_team']),
                    'prob':       round(r['prob_home'] if pred == 'HOME' else r['prob_away'], 3),
                    'net_diff':   round(r.get('net_diff', 0), 2),
                    'home_b2b':   r.get('home_b2b', False),
                    'away_b2b':   r.get('away_b2b', False),
                    'game_time':  g.get('status', ''),
                    'timestamp':  datetime.now(timezone.utc).isoformat(),
                    'correct':    None,
                    'actual':     None,
                })
        except Exception as e:
            print(f'[Trainer] NBA analyze error: {e}')

    def _analyze_nfl(self):
        try:
            from scrapers.nfl_scraper import get_today_games, get_team_stats
            from models.sabermetrics import nfl_win_probability
            games = get_today_games()
            for g in games[:5]:
                if not self.is_running: break
                gid = str(g['game_id'])
                if self._already_predicted(gid): continue
                if not self._is_future_or_today(g.get('game_time', '')):
                    continue
                self.current_game = f"NFL: {g['away_team']} @ {g['home_team']}"
                h = get_team_stats(str(g['home_id']))
                a = get_team_stats(str(g['away_id']))
                r = nfl_win_probability(h, a)
                pred = 'HOME' if r['prob_home'] > 0.5 else 'AWAY'
                self._save_prediction({
                    'game_id':    gid,
                    'sport':      'NFL',
                    'game':       f"{g['away_team']} @ {g['home_team']}",
                    'home_team':  g['home_team'],
                    'away_team':  g['away_team'],
                    'prediction': pred,
                    'pick_name':  g['home_team'] if pred == 'HOME' else g['away_team'],
                    'prob':       round(r['prob_home'] if pred == 'HOME' else r['prob_away'], 3),
                    'score_diff': round(r.get('score_diff', 0), 2),
                    'game_time':  g.get('game_time', ''),
                    'timestamp':  datetime.now(timezone.utc).isoformat(),
                    'correct':    None,
                    'actual':     None,
                })
        except Exception as e:
            print(f'[Trainer] NFL analyze error: {e}')

    def _analyze_soccer(self):
        try:
            from scrapers.soccer_scraper import get_today_games, get_team_stats, compute_dixon_coles_strength
            from models.sabermetrics import soccer_probabilities
            games = get_today_games()
            for g in games[:5]:
                if not self.is_running: break
                gid = str(g['game_id'])
                if self._already_predicted(gid): continue
                if not self._is_future_or_today(g.get('game_time', '')):
                    continue
                self.current_game = f"Soccer: {g['away_team']} @ {g['home_team']}"
                league = g.get('league', 'epl')
                h  = get_team_stats(str(g['home_id']), league)
                a  = get_team_stats(str(g['away_id']), league)
                dc = compute_dixon_coles_strength(h, a)
                p  = soccer_probabilities(dc['lambda_home'], dc['lambda_away'], dc['rho'])
                best = max([('HOME', p['prob_home']),
                            ('DRAW', p['prob_draw']),
                            ('AWAY', p['prob_away'])], key=lambda x: x[1])
                self._save_prediction({
                    'game_id':    gid,
                    'sport':      'Soccer',
                    'game':       f"{g['away_team']} @ {g['home_team']}",
                    'home_team':  g['home_team'],
                    'away_team':  g['away_team'],
                    'league':     league,
                    'prediction': best[0],
                    'pick_name':  g['home_team'] if best[0]=='HOME' else (g['away_team'] if best[0]=='AWAY' else 'Empate'),
                    'prob':       round(best[1], 3),
                    'lambda_home': dc['lambda_home'],
                    'lambda_away': dc['lambda_away'],
                    'game_time':  g.get('game_time', ''),
                    'timestamp':  datetime.now(timezone.utc).isoformat(),
                    'correct':    None,
                    'actual':     None,
                })
        except Exception as e:
            print(f'[Trainer] Soccer analyze error: {e}')

    def _verify_past_predictions(self):
        """Verifica resultados de predicciones pendientes."""
        pending = [h for h in self.history if h.get('correct') is None]
        changed = False
        for pred in pending[:10]:
            try:
                actual = self._fetch_actual_result(pred)
                if actual is not None:
                    pred['actual']  = actual
                    pred['correct'] = (pred['prediction'] == actual)
                    changed = True
            except Exception as e:
                print(f'[Trainer] Verify error: {e}')
        if changed:
            self._save_history()

    def _fetch_actual_result(self, pred: dict):
        sport = pred.get('sport', '')
        gid   = pred.get('game_id', '')
        try:
            if sport == 'MLB':
                from scrapers.mlb_scraper import _get
                data = _get(f'/game/{gid}/linescore')
                if data:
                    home_r = data.get('teams', {}).get('home', {}).get('runs')
                    away_r = data.get('teams', {}).get('away', {}).get('runs')
                    if home_r is not None and away_r is not None and home_r != away_r:
                        return 'HOME' if home_r > away_r else 'AWAY'
            elif sport == 'NBA':
                from scrapers.nba_scraper import _nba_get
                data = _nba_get('boxscoresummaryv2', {'GameID': gid})
                if data:
                    rs   = {r['name']: r for r in data.get('resultSets', [])}
                    line = rs.get('LineScore', {})
                    rows = line.get('rowSet', [])
                    if len(rows) >= 2:
                        h_pts = rows[0][22] if len(rows[0]) > 22 else None
                        a_pts = rows[1][22] if len(rows[1]) > 22 else None
                        if h_pts and a_pts:
                            return 'HOME' if h_pts > a_pts else 'AWAY'
        except Exception as e:
            print(f'[Trainer] Fetch result error: {e}')
        return None

    # ---- Persistencia ----
    def _already_predicted(self, game_id: str) -> bool:
        return any(h['game_id'] == game_id for h in self.history)

    def _save_prediction(self, pred: dict):
        self.history.append(pred)
        self._save_history()
        print(f'[Trainer] Guardado: {pred["sport"]} - {pred["game"]} -> {pred["prediction"]} ({pred["prob"]*100:.1f}%)')

    def _save_history(self):
        HISTORY_FILE.parent.mkdir(exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history, f, indent=2, default=str)

    def _load_history(self) -> list:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE) as f:
                    return json.load(f)
            except:
                pass
        return []
