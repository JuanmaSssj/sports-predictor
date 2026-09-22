"""
Sistema de Auto-Entrenamiento de la IA.
Analiza partidos, hace predicciones, verifica resultados y actualiza win rate.
NO usa la Odds API durante entrenamiento para conservar consultas.
"""
import json
import time
import threading
from datetime import datetime, date
from pathlib import Path

from scrapers.mlb_scraper  import get_today_games as mlb_games, get_full_game_data
from scrapers.nba_scraper  import get_today_games as nba_games, get_team_advanced_stats, is_back_to_back
from scrapers.nfl_scraper  import get_today_games as nfl_games, get_team_stats as nfl_team_stats
from scrapers.soccer_scraper import get_today_games as soccer_games, get_team_stats as soccer_team_stats, compute_dixon_coles_strength
from models.sabermetrics   import mlb_game_score, nba_win_probability, nfl_win_probability, soccer_probabilities

HISTORY_FILE = Path('data/training_history.json')


class AutoTrainer:
    """
    Entrenador automatico de la IA.
    - Analiza partidos proximos/en vivo sin usar Odds API
    - Hace predicciones y las guarda
    - Verifica resultados y actualiza win rate
    - Ciclo cada 30 minutos
    """

    def __init__(self):
        self.is_running    = False
        self._thread       = None
        self.history       = self._load_history()
        self.current_status = 'Inactivo'
        self.current_game   = ''

    # ---- Propiedades calculadas ----

    @property
    def total_analyzed(self) -> int:
        return len(self.history)

    @property
    def total_correct(self) -> int:
        return sum(1 for h in self.history if h.get('correct') is True)

    @property
    def win_rate(self) -> float:
        resolved = [h for h in self.history if h.get('correct') is not None]
        if not resolved:
            return 0.0
        return round(sum(1 for h in resolved if h['correct']) / len(resolved) * 100, 1)

    @property
    def last_10(self) -> list:
        resolved = [h for h in self.history if h.get('correct') is not None]
        return [('W' if h['correct'] else 'L') for h in resolved[-10:]]

    # ---- Control ----

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        self.current_status = 'Detenido'

    def get_status(self) -> dict:
        return {
            'is_running':      self.is_running,
            'status':          self.current_status,
            'current_game':    self.current_game,
            'total_analyzed':  self.total_analyzed,
            'total_correct':   self.total_correct,
            'win_rate':        self.win_rate,
            'last_10':         self.last_10,
            'history_count':   len(self.history),
        }

    def get_history(self) -> list:
        return list(reversed(self.history[-50:]))

    # ---- Loop principal ----

    def _loop(self):
        while self.is_running:
            try:
                self.current_status = 'Buscando partidos...'
                self._analyze_all_sports()
                self._verify_past_predictions()
                self.current_status = f'Esperando... proximo ciclo en 30 min'
                self.current_game   = ''
                # Esperar 30 minutos en intervalos de 10s para poder detener
                for _ in range(180):
                    if not self.is_running:
                        break
                    time.sleep(10)
            except Exception as e:
                print(f'[Trainer] Loop error: {e}')
                time.sleep(60)

    def _analyze_all_sports(self):
        """Analiza partidos de todos los deportes y guarda predicciones."""
        sports_fetchers = [
            ('MLB',    self._analyze_mlb),
            ('NBA',    self._analyze_nba),
            ('NFL',    self._analyze_nfl),
            ('Soccer', self._analyze_soccer),
        ]
        for sport_name, fetcher in sports_fetchers:
            if not self.is_running:
                break
            try:
                self.current_status = f'Analizando {sport_name}...'
                fetcher()
            except Exception as e:
                print(f'[Trainer] {sport_name} error: {e}')

    def _analyze_mlb(self):
        games = mlb_games()
        for g in games[:5]:  # max 5 por ciclo
            if not self.is_running:
                break
            if self._already_predicted(g['game_id']):
                continue
            self.current_game = f"MLB: {g['away_team']} @ {g['home_team']}"
            try:
                full = get_full_game_data(g)
                score = mlb_game_score(
                    full.get('home_batting', {}),
                    full.get('away_batting', {}),
                    full.get('home_pitcher_stats', {}),
                    full.get('away_pitcher_stats', {}),
                )
                prediction = 'HOME' if score['prob_home'] > 0.5 else 'AWAY'
                self._save_prediction({
                    'game_id':    str(g['game_id']),
                    'sport':      'MLB',
                    'game':       self.current_game,
                    'prediction': prediction,
                    'prob':       score['prob_home'] if prediction == 'HOME' else score['prob_away'],
                    'home_team':  g['home_team'],
                    'away_team':  g['away_team'],
                    'timestamp':  datetime.utcnow().isoformat(),
                    'correct':    None,
                    'actual':     None,
                })
            except Exception as e:
                print(f'[Trainer] MLB game error: {e}')

    def _analyze_nba(self):
        games = nba_games()
        for g in games[:5]:
            if not self.is_running:
                break
            if self._already_predicted(g['game_id']):
                continue
            self.current_game = f"NBA: {g['away_team']} @ {g['home_team']}"
            try:
                h_stats = get_team_advanced_stats(g['home_team'])
                a_stats = get_team_advanced_stats(g['away_team'])
                h_b2b   = is_back_to_back(g['home_team'])
                a_b2b   = is_back_to_back(g['away_team'])
                result  = nba_win_probability(h_stats, a_stats, h_b2b, a_b2b)
                prediction = 'HOME' if result['prob_home'] > 0.5 else 'AWAY'
                self._save_prediction({
                    'game_id':    str(g['game_id']),
                    'sport':      'NBA',
                    'game':       self.current_game,
                    'prediction': prediction,
                    'prob':       result['prob_home'] if prediction == 'HOME' else result['prob_away'],
                    'home_team':  str(g['home_team']),
                    'away_team':  str(g['away_team']),
                    'timestamp':  datetime.utcnow().isoformat(),
                    'correct':    None,
                    'actual':     None,
                })
            except Exception as e:
                print(f'[Trainer] NBA game error: {e}')

    def _analyze_nfl(self):
        games = nfl_games()
        for g in games[:5]:
            if not self.is_running:
                break
            if self._already_predicted(g['game_id']):
                continue
            self.current_game = f"NFL: {g['away_team']} @ {g['home_team']}"
            try:
                h_stats = nfl_team_stats(g['home_id'])
                a_stats = nfl_team_stats(g['away_id'])
                result  = nfl_win_probability(h_stats, a_stats)
                prediction = 'HOME' if result['prob_home'] > 0.5 else 'AWAY'
                self._save_prediction({
                    'game_id':    str(g['game_id']),
                    'sport':      'NFL',
                    'game':       self.current_game,
                    'prediction': prediction,
                    'prob':       result['prob_home'] if prediction == 'HOME' else result['prob_away'],
                    'home_team':  g['home_team'],
                    'away_team':  g['away_team'],
                    'timestamp':  datetime.utcnow().isoformat(),
                    'correct':    None,
                    'actual':     None,
                })
            except Exception as e:
                print(f'[Trainer] NFL game error: {e}')

    def _analyze_soccer(self):
        games = soccer_games()
        for g in games[:5]:
            if not self.is_running:
                break
            if self._already_predicted(g['game_id']):
                continue
            self.current_game = f"Soccer: {g['away_team']} @ {g['home_team']}"
            try:
                h_stats = soccer_team_stats(g['home_id'], g.get('league', 'epl'))
                a_stats = soccer_team_stats(g['away_id'], g.get('league', 'epl'))
                dc      = compute_dixon_coles_strength(h_stats, a_stats)
                probs   = soccer_probabilities(dc['lambda_home'], dc['lambda_away'], dc['rho'])
                best    = max([('HOME', probs['prob_home']),
                               ('DRAW', probs['prob_draw']),
                               ('AWAY', probs['prob_away'])],
                              key=lambda x: x[1])
                self._save_prediction({
                    'game_id':    str(g['game_id']),
                    'sport':      'Soccer',
                    'game':       self.current_game,
                    'prediction': best[0],
                    'prob':       best[1],
                    'home_team':  g['home_team'],
                    'away_team':  g['away_team'],
                    'timestamp':  datetime.utcnow().isoformat(),
                    'correct':    None,
                    'actual':     None,
                })
            except Exception as e:
                print(f'[Trainer] Soccer game error: {e}')

    def _verify_past_predictions(self):
        """Verifica predicciones pendientes contra resultados reales."""
        pending = [h for h in self.history if h.get('correct') is None]
        for pred in pending[:10]:
            try:
                actual = self._fetch_actual_result(pred)
                if actual is not None:
                    pred['actual']  = actual
                    pred['correct'] = (pred['prediction'] == actual)
        self._save_history()

    def _fetch_actual_result(self, pred: dict) -> str | None:
        """Obtiene resultado real del partido si ya termino."""
        sport = pred.get('sport', '')
        gid   = pred.get('game_id', '')
        try:
            if sport == 'MLB':
                from scrapers.mlb_scraper import _get
                data = _get(f'/game/{gid}/linescore')
                if data:
                    home_r = data.get('teams', {}).get('home', {}).get('runs', None)
                    away_r = data.get('teams', {}).get('away', {}).get('runs', None)
                    if home_r is not None and away_r is not None:
                        if home_r > away_r:
                            return 'HOME'
                        elif away_r > home_r:
                            return 'AWAY'
            elif sport == 'NBA':
                from scrapers.nba_scraper import _nba_get
                data = _nba_get('boxscoresummaryv2', {'GameID': gid})
                if data:
                    rs = {r['name']: r for r in data.get('resultSets', [])}
                    line = rs.get('LineScore', {})
                    rows = line.get('rowSet', [])
                    if len(rows) >= 2:
                        h_pts = rows[0][22] if len(rows[0]) > 22 else None
                        a_pts = rows[1][22] if len(rows[1]) > 22 else None
                        if h_pts and a_pts:
                            return 'HOME' if h_pts > a_pts else 'AWAY'
        except Exception as e:
            print(f'[Trainer] Verify error: {e}')
        return None

    # ---- Persistencia ----

    def _already_predicted(self, game_id) -> bool:
        return any(h['game_id'] == str(game_id) for h in self.history)

    def _save_prediction(self, pred: dict):
        self.history.append(pred)
        self._save_history()

    def _save_history(self):
        HISTORY_FILE.parent.mkdir(exist_ok=True)
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history, f, indent=2)

    def _load_history(self) -> list:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE) as f:
                    return json.load(f)
            except:
                pass
        return []
