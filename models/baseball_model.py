"""
Modelo de predicción para MLB.
Combina: Pitcher Quality (FIP, K/9, BB/9), Team Offense (wOBA, R/G),
record del equipo y ventaja de localía.
"""
import math


def predict_baseball_game(home_data: dict, away_data: dict,
                          league_avg_era: float = 4.20,
                          home_field_adv: float = 0.54) -> dict:
    """
    Predice probabilidad de victoria home/away y total esperado de carreras.

    Args:
        home_data: dict con pitcher_stats, batting, record del equipo local
        away_data: dict con pitcher_stats, batting, record del equipo visitante
        league_avg_era: ERA promedio de la liga (default 4.20)
        home_field_adv: prob. histórica de que gane el local (default 0.54)

    Returns:
        dict con prob_home, prob_away, expected_total, home_strength, away_strength
    """

    # --- PITCHER QUALITY SCORE ---
    def pitcher_score(p: dict) -> float:
        fip = p.get('fip') or league_avg_era
        k9  = p.get('k9') or 7.0
        bb9 = p.get('bb9') or 3.5
        # FIP bajo = bueno. K/9 alto = bueno. BB/9 bajo = bueno.
        score = (league_avg_era / max(fip, 1.5)) * (k9 / 7.0) * (3.5 / max(bb9, 0.5))
        return max(score, 0.30)  # floor

    # --- OFFENSE QUALITY SCORE ---
    def offense_score(b: dict) -> float:
        woba = b.get('woba') or 0.320
        rpg  = b.get('runs_per_game') or 4.50
        # wOBA promedio MLB ~.320, R/G promedio ~4.50
        return (woba / 0.320) * (rpg / 4.50)

    # --- TEAM STRENGTH ---
    home_strength = pitcher_score(home_data.get('pitcher_stats', {})) * \
                    offense_score(home_data.get('batting', {}))
    away_strength = pitcher_score(away_data.get('pitcher_stats', {})) * \
                    offense_score(away_data.get('batting', {}))

    # --- AJUSTE POR WIN_PCT ---
    home_wp = home_data.get('record', {}).get('win_pct', 0.500)
    away_wp = away_data.get('record', {}).get('win_pct', 0.500)
    home_strength *= (0.70 + 0.60 * home_wp)
    away_strength *= (0.70 + 0.60 * away_wp)

    # --- PROBABILIDAD VÍA LOG-ODDS ---
    if home_strength <= 0 or away_strength <= 0:
        prob_home = 0.50
    else:
        log_odds = math.log(home_strength / away_strength) + \
                   math.log(home_field_adv / (1 - home_field_adv))
        prob_home = 1 / (1 + math.exp(-log_odds))

    prob_home = max(0.15, min(0.85, prob_home))  # clamp razonable
    prob_away = 1 - prob_home

    # --- TOTAL ESPERADO (carreras) ---
    home_fip = home_data.get('pitcher_stats', {}).get('fip', league_avg_era) or league_avg_era
    away_fip = away_data.get('pitcher_stats', {}).get('fip', league_avg_era) or league_avg_era
    avg_fip = (home_fip + away_fip) / 2
    expected_total = 8.8 * (league_avg_era / max(avg_fip, 2.5))
    expected_total = max(5.5, min(expected_total, 13.0))  # clamp

    return {
        'prob_home': round(prob_home, 4),
        'prob_away': round(prob_away, 4),
        'expected_total': round(expected_total, 2),
        'home_strength': round(home_strength, 3),
        'away_strength': round(away_strength, 3),
    }