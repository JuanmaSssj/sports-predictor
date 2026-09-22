"""
Calculadora de Edge, EV+, Kelly y generador de picks.
Usa TODOS los mercados disponibles: ML, spread, totales.
"""
import math


def american_to_prob(american):
    if american is None: return 0.5
    try:
        american = float(american)
        if american > 0: return 100 / (american + 100)
        return abs(american) / (abs(american) + 100)
    except: return 0.5


def prob_to_american(prob: float) -> int:
    if prob <= 0.01 or prob >= 0.99: return 0
    if prob >= 0.5: return round(-prob / (1 - prob) * 100)
    return round((1 - prob) / prob * 100)


def remove_overround(probs: list) -> list:
    total = sum(probs)
    if total <= 0: return probs
    return [p / total for p in probs]


def kelly_fraction(model_prob: float, market_prob: float, fraction: float = 0.25) -> float:
    if market_prob <= 0 or market_prob >= 1: return 0.0
    b = (1 / market_prob) - 1
    q = 1 - model_prob
    kelly = (model_prob * b - q) / b
    return round(max(0.0, min(kelly * fraction, 0.15)), 4)  # cap 15%


def calculate_edge_and_signal(
    model_prob: float,
    market_prob: float,
    sharp_direction: str = 'NEUTRAL',
    vpin_data: dict = None,
    bet_side: str = 'HOME',
    min_edge: float = 0.03,
    bankroll: float = 10_000.0,
) -> dict:
    if vpin_data is None: vpin_data = {}
    if market_prob <= 0: market_prob = 0.5

    raw_edge = model_prob - market_prob

    sharp_aligned = False
    if bet_side in ('HOME', 'OVER', 'YES'):
        sharp_aligned = sharp_direction in ('YES', 'BUY', 'SHARP_BUY')
    else:
        sharp_aligned = sharp_direction in ('NO', 'SELL', 'SHARP_SELL')

    sharp_mult = 1.15 if sharp_aligned else (0.90 if sharp_direction != 'NEUTRAL' else 1.0)
    vpin_spike = vpin_data.get('sharp_active', False)
    vpin_mult  = 1.15 if vpin_spike else 1.0
    adj_edge   = raw_edge * sharp_mult * vpin_mult

    if adj_edge >= 0.06:
        signal = 'BUY'
        confidence = 'ALTA' if (adj_edge >= 0.09 and sharp_aligned) else ('MEDIA' if adj_edge >= 0.045 else 'BAJA')
    elif adj_edge >= min_edge:
        signal = 'BUY'
        confidence = 'BAJA'
    elif adj_edge <= -0.06:
        signal = 'SELL'
        confidence = 'MEDIA' if adj_edge <= -0.09 else 'BAJA'
    else:
        signal = 'HOLD'
        confidence = 'N/A'

    kf = kelly_fraction(model_prob, market_prob)
    payout = (1 / market_prob - 1) if market_prob > 0 else 1.0
    ev = model_prob * payout - (1 - model_prob)

    return {
        'raw_edge':      round(raw_edge, 4),
        'adjusted_edge': round(adj_edge, 4),
        'ev':            round(ev, 4),
        'signal':        signal,
        'confidence':    confidence,
        'sharp_aligned': sharp_aligned,
        'vpin_spike':    vpin_spike,
        'kelly_quarter': kf,
        'kelly_usd':     round(kf * bankroll, 2),
        'model_prob':    round(model_prob, 4),
        'market_prob':   round(market_prob, 4),
    }


def generate_picks(games_analysis: list, sport: str) -> dict:
    """
    Genera picks de TODOS los mercados disponibles:
    ML home, ML away, Over, Under, Spread.
    Busca valor real en cada mercado.
    """
    candidates = []

    for g in games_analysis:
        model  = g.get('model', {})
        edge_d = g.get('edge', {})
        mc     = g.get('totals_mc', {})
        home   = g.get('home_team', '')
        away   = g.get('away_team', '')
        game_str = f"{away} @ {home}"
        time_str = g.get('time_mx', '')

        # --- ML Home ---
        ml_home = g.get('ml_home')
        if ml_home is not None:
            mkt_prob_h = american_to_prob(ml_home)
            mdl_prob_h = model.get('prob_home', 0.5)
            raw = mdl_prob_h - mkt_prob_h
            if abs(raw) > 0.02:
                candidates.append({
                    'game':       game_str,
                    'time_mx':    time_str,
                    'pick':       home,
                    'market':     'ML',
                    'side':       'HOME',
                    'moneyline':  ml_home,
                    'model_prob': round(mdl_prob_h, 3),
                    'mkt_prob':   round(mkt_prob_h, 3),
                    'edge':       round(raw, 4),
                    'ev':         round(mdl_prob_h * (100/abs(ml_home) if ml_home < 0 else ml_home/100) - (1-mdl_prob_h), 4),
                    'kelly':      kelly_fraction(mdl_prob_h, mkt_prob_h),
                    'kelly_usd':  round(kelly_fraction(mdl_prob_h, mkt_prob_h) * 10000, 2),
                    'confidence': _confidence(raw),
                })

        # --- ML Away ---
        ml_away = g.get('ml_away')
        if ml_away is not None:
            mkt_prob_a = american_to_prob(ml_away)
            mdl_prob_a = model.get('prob_away', 0.5)
            raw = mdl_prob_a - mkt_prob_a
            if abs(raw) > 0.02:
                candidates.append({
                    'game':       game_str,
                    'time_mx':    time_str,
                    'pick':       away,
                    'market':     'ML',
                    'side':       'AWAY',
                    'moneyline':  ml_away,
                    'model_prob': round(mdl_prob_a, 3),
                    'mkt_prob':   round(mkt_prob_a, 3),
                    'edge':       round(raw, 4),
                    'ev':         round(mdl_prob_a * (100/abs(ml_away) if ml_away < 0 else ml_away/100) - (1-mdl_prob_a), 4),
                    'kelly':      kelly_fraction(mdl_prob_a, mkt_prob_a),
                    'kelly_usd':  round(kelly_fraction(mdl_prob_a, mkt_prob_a) * 10000, 2),
                    'confidence': _confidence(raw),
                })

        # --- Over ---
        total_line = g.get('total_line')
        over_prob  = mc.get('over_prob') or mc.get('over_2.5')
        if total_line and over_prob:
            mkt_over = 0.5238  # -110 tipico
            raw_over = over_prob - mkt_over
            if raw_over > 0.02:
                candidates.append({
                    'game':       game_str,
                    'time_mx':    time_str,
                    'pick':       f'Over {total_line}',
                    'market':     'TOTAL',
                    'side':       'OVER',
                    'moneyline':  -110,
                    'model_prob': round(over_prob, 3),
                    'mkt_prob':   round(mkt_over, 3),
                    'edge':       round(raw_over, 4),
                    'ev':         round(over_prob * 0.909 - (1-over_prob), 4),
                    'kelly':      kelly_fraction(over_prob, mkt_over),
                    'kelly_usd':  round(kelly_fraction(over_prob, mkt_over) * 10000, 2),
                    'confidence': _confidence(raw_over),
                })

        # --- Under ---
        under_prob = mc.get('under_prob') or (1 - over_prob if over_prob else None)
        if total_line and under_prob:
            mkt_under = 0.5238
            raw_under = under_prob - mkt_under
            if raw_under > 0.02:
                candidates.append({
                    'game':       game_str,
                    'time_mx':    time_str,
                    'pick':       f'Under {total_line}',
                    'market':     'TOTAL',
                    'side':       'UNDER',
                    'moneyline':  -110,
                    'model_prob': round(under_prob, 3),
                    'mkt_prob':   round(mkt_under, 3),
                    'edge':       round(raw_under, 4),
                    'ev':         round(under_prob * 0.909 - (1-under_prob), 4),
                    'kelly':      kelly_fraction(under_prob, mkt_under),
                    'kelly_usd':  round(kelly_fraction(under_prob, mkt_under) * 10000, 2),
                    'confidence': _confidence(raw_under),
                })

    # Ordenar por edge descendente
    candidates.sort(key=lambda x: x['edge'], reverse=True)

    # ---- Apuesta Fuerte ----
    # Mejor pick con edge > 4%, momio entre -180 y +200
    apuesta_fuerte = None
    for c in candidates:
        ml = c['moneyline']
        if c['edge'] >= 0.04 and -180 <= ml <= 200:
            apuesta_fuerte = {
                'game':       c['game'],
                'time_mx':    c['time_mx'],
                'pick':       c['pick'],
                'market':     c['market'],
                'moneyline':  ml,
                'model_prob': c['model_prob'],
                'mkt_prob':   c['mkt_prob'],
                'edge':       c['edge'],
                'ev':         c['ev'],
                'confidence': c['confidence'],
                'kelly_usd':  c['kelly_usd'],
                'reasoning':  f"Modelo: {c['model_prob']*100:.1f}% | Mercado: {c['mkt_prob']*100:.1f}% | Edge: +{c['edge']*100:.1f}%",
            }
            break

    # ---- Parlay Ganador (2 patas, combinado >= +100) ----
    parlay_ganador = []
    used = set()
    for c in candidates:
        if len(parlay_ganador) >= 2: break
        if c['game'] in used: continue
        if c['edge'] >= 0.025:
            parlay_ganador.append(c)
            used.add(c['game'])

    # ---- Parlay Ratonero (6-7 patas seguras, momio feo) ----
    parlay_ratonero = []
    used2 = set()
    # Incluir picks con alta probabilidad del modelo (>60%) aunque momio sea feo
    high_prob = sorted(candidates, key=lambda x: x['model_prob'], reverse=True)
    for c in high_prob:
        if len(parlay_ratonero) >= 7: break
        if c['game'] in used2: continue
        if c['model_prob'] >= 0.58:  # modelo dice 58%+ de ganar
            parlay_ratonero.append(c)
            used2.add(c['game'])

    combined_rat = _combine_american_odds([p['moneyline'] for p in parlay_ratonero])

    # ---- Props (mejores picks de totales y spreads) ----
    props = [c for c in candidates if c['market'] == 'TOTAL'][:4]

    return {
        'apuesta_fuerte':  apuesta_fuerte,
        'parlay_ganador':  parlay_ganador,
        'parlay_ratonero': {'picks': parlay_ratonero, 'combined_odds': combined_rat},
        'props':           props,
        'total_candidates': len(candidates),
    }


def _confidence(edge: float) -> str:
    if edge >= 0.09: return 'ALTA'
    if edge >= 0.05: return 'MEDIA'
    if edge >= 0.03: return 'BAJA'
    return 'N/A'


def _combine_american_odds(odds_list: list) -> int:
    if not odds_list: return 0
    decimal = 1.0
    for o in odds_list:
        if o is None: continue
        try:
            o = float(o)
            decimal *= (o/100 + 1) if o > 0 else (100/abs(o) + 1)
        except: continue
    if decimal <= 1: return 0
    american = (decimal - 1) * 100 if decimal >= 2 else -(100 / (decimal - 1))
    return round(american)
