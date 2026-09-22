"""
Sports Predictor AI - Servidor Flask
Timezone: America/Mexico_City
"""
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, render_template

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key')
MEXICO_TZ = ZoneInfo('America/Mexico_City')

# ---- Imports con fallback ----
try:
    from scrapers.odds_scraper import (get_games_with_odds, get_upcoming_games,
                                        american_to_prob as a2p)
    ODDS_OK = True
except Exception as e:
    print(f'[WARN] odds_scraper: {e}'); ODDS_OK = False

try:
    from scrapers.mlb_scraper import get_today_games as mlb_today, get_full_game_data
    MLB_OK = True
except Exception as e:
    print(f'[WARN] mlb_scraper: {e}'); MLB_OK = False

try:
    from scrapers.nba_scraper import (get_today_games as nba_today,
                                       get_team_advanced_stats, is_back_to_back)
    NBA_OK = True
except Exception as e:
    print(f'[WARN] nba_scraper: {e}'); NBA_OK = False

try:
    from scrapers.nfl_scraper import get_today_games as nfl_today, get_team_stats as nfl_stats
    NFL_OK = True
except Exception as e:
    print(f'[WARN] nfl_scraper: {e}'); NFL_OK = False

try:
    from scrapers.soccer_scraper import (get_today_games as soccer_today,
                                          get_team_stats as soccer_stats,
                                          compute_dixon_coles_strength)
    SOCCER_OK = True
except Exception as e:
    print(f'[WARN] soccer_scraper: {e}'); SOCCER_OK = False

try:
    from scrapers.injuries_scraper import get_team_injury_impact
    INJ_OK = True
except Exception as e:
    print(f'[WARN] injuries_scraper: {e}'); INJ_OK = False

try:
    from scrapers.weather_scraper import get_weather
    WX_OK = True
except Exception as e:
    print(f'[WARN] weather_scraper: {e}'); WX_OK = False

try:
    from scrapers.sharp_money_scraper import get_combined_sharp_signal
    SHARP_OK = True
except Exception as e:
    print(f'[WARN] sharp_money_scraper: {e}'); SHARP_OK = False

try:
    from models.sabermetrics import (mlb_game_score, nba_win_probability,
                                      nfl_win_probability, soccer_probabilities)
    from models.monte_carlo import monte_carlo_soccer, monte_carlo_totals
    from models.edge_calculator import (calculate_edge_and_signal,
                                         american_to_prob as a2p,
                                         generate_picks)
    MODELS_OK = True
except Exception as e:
    print(f'[WARN] models: {e}'); MODELS_OK = False

try:
    from models.trainer import AutoTrainer
    trainer = AutoTrainer()
    # Auto-arrancar entrenamiento al iniciar
    trainer.start()
    TRAINER_OK = True
    print('[INFO] Auto-trainer iniciado')
except Exception as e:
    print(f'[WARN] trainer: {e}'); TRAINER_OK = False; trainer = None


# ============================================================
# RUTAS
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/health')
def health():
    now_mx = datetime.now(tz=MEXICO_TZ).strftime('%d/%m/%Y %I:%M %p CT')
    return jsonify({
        'status': 'ok', 'time_mexico': now_mx,
        'odds': ODDS_OK, 'mlb': MLB_OK, 'nba': NBA_OK,
        'nfl': NFL_OK, 'soccer': SOCCER_OK, 'models': MODELS_OK,
        'trainer': TRAINER_OK,
    })


@app.route('/api/top3/<sport>')
def top3(sport: str):
    """Top 3 juegos de HOY con momios, probabilidades, lesiones, clima."""
    try:
        if not ODDS_OK:
            return jsonify({'games': [], 'message': 'Odds API no disponible'})
        games_raw = get_games_with_odds(sport)
        if not games_raw:
            now_mx = datetime.now(MEXICO_TZ).strftime('%d/%m/%Y')
            return jsonify({'games': [],
                            'message': f'No hay partidos de {sport.upper()} hoy ({now_mx})'})
        enriched = []
        for g in games_raw[:8]:
            try:
                enriched.append(_enrich_game(g, sport))
            except Exception as e:
                print(f'[top3] enrich error: {e}')
                enriched.append(g)
        enriched.sort(
            key=lambda x: abs(x.get('edge', {}).get('adjusted_edge', 0) or 0),
            reverse=True
        )
        now_mx = datetime.now(MEXICO_TZ).strftime('%d/%m/%Y %I:%M %p CT')
        return jsonify({'games': enriched[:3], 'sport': sport, 'updated': now_mx})
    except Exception as e:
        return jsonify({'error': str(e), 'games': []}), 500


@app.route('/api/upcoming/<sport>')
def upcoming(sport: str):
    """Proximos partidos en los siguientes 3 dias."""
    try:
        if not ODDS_OK:
            return jsonify({'games': [], 'message': 'Odds API no disponible'})
        games = get_upcoming_games(sport, days=3)
        return jsonify({'games': games[:9], 'sport': sport})
    except Exception as e:
        return jsonify({'error': str(e), 'games': []}), 500


@app.route('/api/picks/<sport>')
def picks(sport: str):
    try:
        if not ODDS_OK:
            return jsonify({'message': 'Odds API no disponible', 'picks': {}})
        games_raw = get_games_with_odds(sport)
        if not games_raw:
            return jsonify({'message': f'No hay partidos de {sport.upper()} hoy', 'picks': {}})
        analyzed = []
        for g in games_raw[:10]:
            try:
                analyzed.append(_enrich_game(g, sport))
            except Exception as e:
                print(f'[picks] error: {e}')
                analyzed.append(g)
        picks_result = generate_picks(analyzed, sport) if MODELS_OK else {}
        now_mx = datetime.now(MEXICO_TZ).strftime('%d/%m/%Y %I:%M %p CT')
        return jsonify({'picks': picks_result, 'sport': sport, 'updated': now_mx})
    except Exception as e:
        return jsonify({'error': str(e), 'picks': {}}), 500


# ---- Entrenamiento ----

@app.route('/api/training/start', methods=['POST'])
def training_start():
    if not TRAINER_OK or not trainer:
        return jsonify({'status': 'error', 'message': 'Trainer no disponible'})
    trainer.start()
    return jsonify({'status': 'started'})


@app.route('/api/training/stop', methods=['POST'])
def training_stop():
    if trainer: trainer.stop()
    return jsonify({'status': 'stopped'})


@app.route('/api/training/status')
def training_status():
    if not trainer:
        return jsonify({'is_running': False, 'status': 'No disponible',
                        'win_rate': 0, 'total_analyzed': 0,
                        'total_correct': 0, 'last_10': []})
    return jsonify(trainer.get_status())


@app.route('/api/training/history')
def training_history():
    if not trainer: return jsonify({'history': []})
    return jsonify({'history': trainer.get_history()})


# ============================================================
# ENRIQUECIMIENTO
# ============================================================

def _enrich_game(g: dict, sport: str) -> dict:
    result = dict(g)
    model  = {'prob_home': 0.5, 'prob_away': 0.5}

    if MODELS_OK:
        try: model = _get_model_probs(g, sport)
        except Exception as e: print(f'[enrich] model: {e}')
    result['model'] = model

    # Edge
    result['edge']  = {'signal': 'HOLD', 'adjusted_edge': 0, 'confidence': 'N/A'}
    result['sharp'] = {'combined_direction': 'NEUTRAL', 'sharp_active': False}
    if MODELS_OK:
        try:
            ml_prob = a2p(g.get('ml_home')) if g.get('ml_home') else 0.5
            sharp   = get_combined_sharp_signal() if SHARP_OK else {'combined_direction': 'NEUTRAL', 'sharp_active': False}
            edge    = calculate_edge_and_signal(
                model_prob=model.get('prob_home', 0.5),
                market_prob=ml_prob,
                sharp_direction=sharp.get('combined_direction', 'NEUTRAL'),
                vpin_data={}, bet_side='HOME',
            )
            result['edge']     = edge
            result['sharp']    = sharp
            result['pick_side'] = g['home_team'] if edge['signal'] == 'BUY' else g['away_team']
        except Exception as e: print(f'[enrich] edge: {e}')

    # Lesiones
    result['home_injuries'] = {'summary': ''}
    result['away_injuries'] = {'summary': ''}
    if INJ_OK:
        try:
            result['home_injuries'] = get_team_injury_impact(g['home_team'], sport)
            result['away_injuries'] = get_team_injury_impact(g['away_team'], sport)
        except: pass

    # Clima
    result['weather'] = {'description': '', 'impact': 'none'}
    if WX_OK:
        try: result['weather'] = get_weather(g['home_team'], sport)
        except: pass

    # Monte Carlo
    if MODELS_OK:
        try:
            if sport == 'soccer' and model.get('dc_params'):
                dc = model['dc_params']
                mc = monte_carlo_soccer(dc.get('lambda_home', 1.3), dc.get('lambda_away', 1.1))
                result['totals_mc'] = {'over_1.5': mc['over_1.5'], 'over_2.5': mc['over_2.5'],
                                        'over_3.5': mc['over_3.5'], 'btts': mc['btts']}
            elif sport in ('nba', 'nfl', 'baseball'):
                exp  = model.get('expected_total') or g.get('total_line') or 220
                line = g.get('total_line') or exp
                std  = 12 if sport == 'nba' else (7 if sport == 'nfl' else 2.5)
                mc   = monte_carlo_totals(float(exp), float(std), float(line))
                result['totals_mc'] = {'over_prob': mc['over_prob'], 'under_prob': mc['under_prob'],
                                        'line': line, 'expected': exp}
        except Exception as e: print(f'[enrich] mc: {e}')

    result['reasoning'] = _build_reasoning(result, sport)
    return result


def _get_model_probs(g: dict, sport: str) -> dict:
    home_id = g.get('home_id', '')
    away_id = g.get('away_id', '')
    if sport == 'baseball' and MLB_OK:
        full = get_full_game_data(g)
        return {**mlb_game_score(full.get('home_batting', {}), full.get('away_batting', {}),
                                  full.get('home_pitcher_stats', {}), full.get('away_pitcher_stats', {})),
                'sport': 'MLB'}
    elif sport == 'nba' and NBA_OK:
        h = get_team_advanced_stats(int(home_id)) if home_id else {}
        a = get_team_advanced_stats(int(away_id)) if away_id else {}
        return {**nba_win_probability(h, a,
                                       is_back_to_back(int(home_id)) if home_id else False,
                                       is_back_to_back(int(away_id)) if away_id else False),
                'sport': 'NBA'}
    elif sport == 'nfl' and NFL_OK:
        h = nfl_stats(str(home_id)) if home_id else {}
        a = nfl_stats(str(away_id)) if away_id else {}
        return {**nfl_win_probability(h, a), 'sport': 'NFL'}
    elif sport == 'soccer' and SOCCER_OK:
        league = g.get('sport', 'soccer_epl').replace('soccer_', '').replace('_', '')
        h = soccer_stats(str(home_id), league) if home_id else {}
        a = soccer_stats(str(away_id), league) if away_id else {}
        dc = compute_dixon_coles_strength(h, a)
        return {**soccer_probabilities(dc['lambda_home'], dc['lambda_away'], dc['rho']),
                'dc_params': dc, 'sport': 'Soccer'}
    return {'prob_home': 0.5, 'prob_away': 0.5, 'expected_total': 0}


def _build_reasoning(g: dict, sport: str) -> str:
    parts = []
    model = g.get('model', {})
    edge  = g.get('edge', {})
    ph    = model.get('prob_home', 0.5)
    parts.append(f'Modelo: {ph*100:.1f}% local')
    adj = edge.get('adjusted_edge', 0) or 0
    if adj > 0: parts.append(f'Edge +{adj*100:.1f}%')
    if edge.get('sharp_aligned'): parts.append('Sharp money alineado')
    if g.get('home_injuries', {}).get('key_players_out'): parts.append(g['home_injuries'].get('summary', ''))
    if g.get('away_injuries', {}).get('key_players_out'): parts.append(g['away_injuries'].get('summary', ''))
    if g.get('weather', {}).get('impact') == 'UNDER': parts.append(g['weather'].get('description', ''))
    return ' | '.join(p for p in parts if p)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
