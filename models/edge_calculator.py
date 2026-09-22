"""
Calculadora de Edge, EV+ y Kelly Criterion.
Ajusta por sharp money y VPIN.
"""


def american_to_prob(american: int) -> float:
    if american is None:
        return 0.5
    if american > 0:
        return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)


def prob_to_american(prob: float) -> int:
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return round(-prob / (1 - prob) * 100)
    return round((1 - prob) / prob * 100)


def remove_overround(probs: list) -> list:
    """Elimina el overround del libro para obtener probabilidades justas."""
    total = sum(probs)
    return [p / total for p in probs]


def calculate_ev(model_prob: float, market_prob: float,
                  payout: float = 1.0) -> float:
    """
    Expected Value = model_prob * payout - (1 - model_prob)
    payout: ganancia neta por unidad apostada (ej. momio -110 -> payout=0.909)
    """
    return model_prob * payout - (1 - model_prob)


def kelly_fraction(model_prob: float, market_prob: float,
                    fraction: float = 0.25) -> float:
    """
    Kelly Criterion con fraccion de seguridad (default 1/4 Kelly).
    f* = (p*b - q) / b
    """
    if market_prob <= 0 or market_prob >= 1:
        return 0.0
    b = (1 / market_prob) - 1  # odds decimales - 1
    q = 1 - model_prob
    kelly = (model_prob * b - q) / b
    return round(max(0, kelly * fraction), 4)


def calculate_edge_and_signal(
    model_prob: float,
    market_prob: float,
    sharp_direction: str = 'NEUTRAL',
    vpin_data: dict = None,
    bet_side: str = 'HOME',
    min_edge: float = 0.045,
    bankroll: float = 10_000.0,
) -> dict:
    """
    Calcula edge ajustado y genera senal de apuesta.

    Ajustes:
    - Sharp money alineado: x1.15
    - Sharp money contrario: x0.85
    - VPIN spike activo: x1.20
    """
    if vpin_data is None:
        vpin_data = {}

    raw_edge = model_prob - market_prob

    # Ajuste sharp money
    sharp_aligned = False
    if bet_side in ('HOME', 'OVER', 'YES'):
        sharp_aligned = sharp_direction in ('YES', 'BUY', 'SHARP_BUY')
    else:
        sharp_aligned = sharp_direction in ('NO', 'SELL', 'SHARP_SELL')

    sharp_mult = 1.15 if sharp_aligned else (0.85 if sharp_direction != 'NEUTRAL' else 1.0)
    edge_sharp = raw_edge * sharp_mult

    # Ajuste VPIN
    vpin_spike = vpin_data.get('sharp_active', False)
    vpin_mult  = 1.20 if vpin_spike else 1.0
    adj_edge   = edge_sharp * vpin_mult

    # Senal
    if adj_edge >= min_edge:
        signal = 'BUY'
        if adj_edge >= 0.08 and sharp_aligned and vpin_spike:
            confidence = 'ALTA'
        elif adj_edge >= 0.055:
            confidence = 'MEDIA'
        else:
            confidence = 'BAJA'
    elif adj_edge <= -min_edge:
        signal = 'SELL'
        confidence = 'MEDIA' if adj_edge <= -0.07 else 'BAJA'
    else:
        signal = 'HOLD'
        confidence = 'N/A'

    kf  = kelly_fraction(model_prob, market_prob)
    ev  = calculate_ev(model_prob, market_prob,
                        payout=(1/market_prob - 1) if market_prob > 0 else 1)

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
    Genera los 4 tipos de picks a partir de la lista de juegos analizados.
    Retorna: {apuesta_fuerte, parlay_ganador, parlay_ratonero, parlay_props}
    """
    # Ordenar por edge ajustado descendente
    sorted_games = sorted(games_analysis,
                          key=lambda g: g.get('edge', {}).get('adjusted_edge', 0),
                          reverse=True)

    apuesta_fuerte = None
    parlay_ganador = []
    parlay_ratonero = []

    for g in sorted_games:
        edge = g.get('edge', {})
        adj  = edge.get('adjusted_edge', 0)
        conf = edge.get('confidence', 'BAJA')
        ml   = g.get('ml_home') or g.get('ml_away')

        # Apuesta Fuerte: edge alto, confianza alta, momio entre -150 y +100
        if (apuesta_fuerte is None and adj >= 0.05 and conf in ('ALTA', 'MEDIA')
                and ml is not None and -150 <= ml <= 100):
            apuesta_fuerte = {
                'game': f"{g['home_team']} vs {g['away_team']}",
                'pick': g.get('pick_side', g['home_team']),
                'moneyline': ml,
                'model_prob': edge.get('model_prob', 0),
                'edge': adj,
                'confidence': conf,
                'kelly_usd': edge.get('kelly_usd', 0),
                'reasoning': g.get('reasoning', ''),
            }

        # Parlay Ganador: 2 picks con edge positivo
        if len(parlay_ganador) < 2 and adj >= 0.03:
            parlay_ganador.append({
                'game': f"{g['home_team']} vs {g['away_team']}",
                'pick': g.get('pick_side', g['home_team']),
                'moneyline': ml,
                'edge': adj,
            })

        # Parlay Ratonero: picks muy seguros con momio feo
        if (len(parlay_ratonero) < 7 and adj >= 0.04
                and conf in ('ALTA', 'MEDIA')
                and ml is not None and ml <= -200):
            parlay_ratonero.append({
                'game': f"{g['home_team']} vs {g['away_team']}",
                'pick': g.get('pick_side', g['home_team']),
                'moneyline': ml,
                'model_prob': edge.get('model_prob', 0),
            })

    # Calcular momio combinado del parlay ratonero
    parlay_rat_combined = _combine_american_odds(
        [p['moneyline'] for p in parlay_ratonero if p.get('moneyline')])

    return {
        'apuesta_fuerte': apuesta_fuerte,
        'parlay_ganador': parlay_ganador,
        'parlay_ratonero': {
            'picks': parlay_ratonero,
            'combined_odds': parlay_rat_combined,
        },
    }


def _combine_american_odds(odds_list: list) -> int:
    """Combina momios americanos en un parlay."""
    if not odds_list:
        return 0
    decimal = 1.0
    for o in odds_list:
        if o is None:
            continue
        if o > 0:
            decimal *= (o / 100 + 1)
        else:
            decimal *= (100 / abs(o) + 1)
    american = (decimal - 1) * 100 if decimal >= 2 else -(100 / (decimal - 1))
    return round(american)
