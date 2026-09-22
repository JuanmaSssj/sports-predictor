"""
Sports Predictor AI - Servidor Flask principal
Rutas: dashboard, top3, picks, training
"""
import json
from datetime import datetime
from flask import Flask, jsonify, render_template, request
from config import FLASK_SECRET

# Importar scrapers
from scrapers.odds_scraper    import get_games_with_odds, american_to_prob
from scrapers.mlb_scraper     import get_today_games as mlb_today, get_full_game_data
from scrapers.nba_scraper     import get_today_games as nba_today, get_team_advanced_stats, is_back_to_back
from scrapers.nfl_scraper     import get_today_games as nfl_today, get_team_stats as nfl_stats, get_team_record
from scrapers.soccer_scraper  import get_today_games as soccer_today, get_team_stats as soccer_stats, compute_dixon_coles_strength
from scrapers.injuries_scraper import get_team_injury_impact
from scrapers.weather_scraper  import get_weather
from scrapers.sharp_money_scraper import get_combined_sharp_signal

# Importar modelos
from models.sabermetrics  import (mlb_game_score, nba_win_probability,
                                   nfl_win_probability, soccer_probabilities)
from models.monte_carlo   import monte_carlo_soccer, monte_carlo_totals
from models.edge_calculator import (calculate_edge_and_signal, american_to_prob as a2p,
                                     generate_picks)
from models.trainer import AutoTrainer

app    = Flask(__name__)
app.secret_key = FLASK_SECRET
trainer = AutoTrainer()


# ============================================================
# RUTAS PRINCIPALES
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/top3/<sport>')
def top3(sport: str):
    """
    Retorna los top 3 partidos del dia para el deporte dado.
    Incluye: probabilidades ML, Over/Under, Handicap, sharp money, lesiones, clima.
    """
    try:
        games_raw = get_games_with_odds(sport)
        if not games_raw:
            return jsonify({'games': [], 'message': f'No hay partidos de {sport} hoy'})

        enriched = []
        for g in games_raw[:6]:  # analizar hasta 6, retornar top 3
            try:
                analysis = _enrich_game(g, sport)
                enriched.append(analysis)
            except Exception as e:
                print(f'[API] Enrich error: {e}')
                continue

        # Ordenar por "importancia": mayor notional de sharp money + mayor edge
        enriched.sort(
            key=lambda x: (
                x.get('sharp', {}).get('sharp_active', False),
                abs(x.get('edge', {}).get('adjusted_edge', 0) or 0)
            ),
            reverse=True
        )

        return jsonify({'games': enriched[:3], 'sport': sport,
                        'updated': datetime.utcnow().isoformat()})
    except Exception as e:
        return jsonify({'error': str(e), 'games': []}), 500


@app.route('/api/picks/<sport>')
def picks(sport: str):
    """
    Genera los 4 tipos de picks para el deporte.
    Apuesta Fuerte, Parlay Ganador, Parlay Ratonero, Props.
    """
    try:
        games_raw = get_games_with_odds(sport)
        if not games_raw:
            return jsonify({'message': f'No hay partidos de {sport} hoy',
                            'picks': {}})

        analyzed = []
        for g in games_raw[:10]:
            try:
                analysis = _enrich_game(g, sport)
                analyzed.append(analysis)
            except Exception as e:
                print(f'[Picks] Error: {e}')

        picks_result = generate_picks(analyzed, sport)
        return jsonify({'picks': picks_result, 'sport': sport,
                        'updated': datetime.utcnow().isoformat()})
    except Exception as e:
        return jsonify({'error': str(e), 'picks': {}}), 500


# ============================================================
# RUTAS DE ENTRENAMIENTO
# ============================================================

@app.route('/api/training/start', methods=['POST'])
def training_start():
    trainer.start()
    return jsonify({'status': 'started', 'message': 'Entrenamiento iniciado'})


@app.route('/api/training/stop', methods=['POST'])
def training_stop():
    trainer.stop()
    return jsonify({'status': 'stopped', 'message': 'Entrenamiento detenido'})


@app.route('/api/training/status')
def training_status():
    return jsonify(trainer.get_status())


@app.route('/api/training/history')
def training_history():
    return jsonify({'history': trainer.get_history()})


# ============================================================
# LOGICA DE ENRIQUECIMIENTO
# ============================================================

def _enrich_game(g: dict, sport: str) -> dict:
    """
    Enriquece un partido con: stats del modelo, sharp money, lesiones, clima.
    """
    home = g['home_team']
    away = g['away_team']

    # --- Probabilidades del modelo ---
    model = _get_model_probs(g, sport)

    # --- Probabilidades del mercado (sin overround) ---
    ml_home_prob = a2p(g.get('ml_home')) if g.get('ml_home') else model.get('prob_home', 0.5)
    ml_away_prob = a2p(g.get('ml_away')) if g.get('ml_away') else model.get('prob_away', 0.5)

    # --- Edge ---
    sharp = get_combined_sharp_signal()  # sin tickers especificos por ahora
    edge  = calculate_edge_and_signal(
        model_prob      = model.get('prob_home', 0.5),
        market_prob     = ml_home_prob,
        sharp_direction = sharp.get('combined_direction', 'NEUTRAL'),
        vpin_data       = {},
        bet_side        = 'HOME',
    )

    # Determinar pick side
    if edge['signal'] == 'BUY':
        pick_side = home
    elif edge['signal'] == 'SELL':
        pick_side = away
    else:
        pick_side = home if model.get('prob_home', 0.5) > 0.5 else away

    # --- Lesiones ---
    home_inj = get_team_injury_impact(home, sport)
    away_inj = get_team_injury_impact(away, sport)

    # --- Clima ---
    weather = get_weather(home, sport)

    # --- Totales Monte Carlo ---
    total_mc = {}
    if sport == 'soccer':
        dc = model.get('dc_params', {})
        if dc:
            mc = monte_carlo_soccer(dc.get('lambda_home', 1.3),
                                     dc.get('lambda_away', 1.1))
            total_mc = {
                'over_1.5': mc['over_1.5'], 'over_2.5': mc['over_2.5'],
                'over_3.5': mc['over_3.5'], 'btts': mc['btts'],
            }
    elif sport in ('nba', 'nfl', 'baseball'):
        exp_total = model.get('expected_total', g.get('total_line', 220))
        line      = g.get('total_line', exp_total)
        std       = 12 if sport == 'nba' else (7 if sport == 'nfl' else 2.5)
        mc = monte_carlo_totals(exp_total, std, line)
        total_mc  = {'over_prob': mc['over_prob'], 'under_prob': mc['under_prob'],
                     'line': line, 'expected': exp_total}

    return {
        **g,
        'model':       model,
        'edge':        edge,
        'pick_side':   pick_side,
        'sharp':       sharp,
        'home_injuries': home_inj,
        'away_injuries': away_inj,
        'weather':     weather,
        'totals_mc':   total_mc,
        'reasoning':   _build_reasoning(model, edge, home_inj, away_inj, weather, sport),
    }


def _get_model_probs(g: dict, sport: str) -> dict:
    """Obtiene probabilidades del modelo segun el deporte."""
    home_id = g.get('home_id', '')
    away_id = g.get('away_id', '')

    if sport == 'baseball':
        full = get_full_game_data(g)
        score = mlb_game_score(
            full.get('home_batting', {}), full.get('away_batting', {}),
            full.get('home_pitcher_stats', {}), full.get('away_pitcher_stats', {}),
        )
        return {**score, 'sport': 'MLB'}

    elif sport == 'nba':
        h_stats = get_team_advanced_stats(int(home_id)) if home_id else {}
        a_stats = get_team_advanced_stats(int(away_id)) if away_id else {}
        h_b2b   = is_back_to_back(int(home_id)) if home_id else False
        a_b2b   = is_back_to_back(int(away_id)) if away_id else False
        result  = nba_win_probability(h_stats, a_stats, h_b2b, a_b2b)
        return {**result, 'sport': 'NBA'}

    elif sport == 'nfl':
        h_stats = nfl_stats(str(home_id)) if home_id else {}
        a_stats = nfl_stats(str(away_id)) if away_id else {}
        result  = nfl_win_probability(h_stats, a_stats)
        return {**result, 'sport': 'NFL'}

    elif sport == 'soccer':
        league  = g.get('sport', 'soccer_epl').replace('soccer_', '').replace('_', '')
        h_stats = soccer_stats(str(home_id), league) if home_id else {}
        a_stats = soccer_stats(str(away_id), league) if away_id else {}
        dc      = compute_dixon_coles_strength(h_stats, a_stats)
        probs   = soccer_probabilities(dc['lambda_home'], dc['lambda_away'], dc['rho'])
        return {**probs, 'dc_params': dc, 'sport': 'Soccer'}

    return {'prob_home': 0.5, 'prob_away': 0.5, 'expected_total': 0}


def _build_reasoning(model: dict, edge: dict, home_inj: dict,
                      away_inj: dict, weather: dict, sport: str) -> str:
    """Construye texto de razonamiento para el pick."""
    parts = []
    ph = model.get('prob_home', 0.5)
    parts.append(f'Modelo: {ph*100:.1f}% local')
    if edge['adjusted_edge'] > 0:
        parts.append(f'Edge +{edge["adjusted_edge"]*100:.1f}%')
    if edge['sharp_aligned']:
        parts.append('Sharp money alineado')
    if home_inj.get('key_players_out'):
        parts.append(f'Bajas local: {home_inj["summary"]}')
    if away_inj.get('key_players_out'):
        parts.append(f'Bajas visit.: {away_inj["summary"]}')
    if weather.get('impact') == 'UNDER':
        parts.append(f'Clima: {weather["description"]}')
    return ' | '.join(parts)


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
