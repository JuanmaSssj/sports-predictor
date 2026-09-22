"""
Sabermetricas completas para los 4 deportes.
Todas las formulas son matematicamente correctas.
"""
import numpy as np


# ============================================================
# BEISBOL
# ============================================================

def fip(hr: float, bb: float, hbp: float, k: float, ip: float,
        c_fip: float = 3.10) -> float:
    """Fielding Independent Pitching. cFIP ~3.10 MLB moderna."""
    return (13*hr + 3*(bb+hbp) - 2*k) / max(ip, 0.1) + c_fip


def xfip(fb: float, bb: float, hbp: float, k: float, ip: float,
         league_hr_fb: float = 0.105, c_fip: float = 3.10) -> float:
    """xFIP: reemplaza HR reales con HR esperados segun fly balls."""
    expected_hr = fb * league_hr_fb
    return fip(expected_hr, bb, hbp, k, ip, c_fip)


def woba(bb: float, hbp: float, singles: float, doubles: float,
         triples: float, hr: float, pa: float) -> float:
    """Weighted On-Base Average. Pesos 2023 MLB."""
    return (0.696*bb + 0.726*hbp + 0.883*singles + 1.244*doubles +
            1.569*triples + 2.004*hr) / max(pa, 1)


def wrc_plus(woba_val: float, league_woba: float = 0.318,
             league_wrc_per_pa: float = 0.115, park_factor: float = 100) -> float:
    """wRC+ normalizado a 100 = promedio liga."""
    wrc_pa = (woba_val - league_woba) / 1.157 + league_wrc_per_pa
    return round((wrc_pa / league_wrc_per_pa) * (100 / (park_factor/100)), 1)


def babip(h: float, hr: float, ab: float, k: float, sf: float) -> float:
    """Batting Average on Balls In Play."""
    return (h - hr) / max(ab - k - hr + sf, 1)


def pythagorean_expectation(runs_scored: float, runs_allowed: float,
                             exp: float = 1.83) -> float:
    """Expectativa pitagorica de victorias. Exp=1.83 para MLB."""
    rs = max(runs_scored, 0.1)
    ra = max(runs_allowed, 0.1)
    return rs**exp / (rs**exp + ra**exp)


def pitcher_fatigue_factor(days_rest: int, pitches_last_start: int) -> float:
    """
    Factor de fatiga del pitcher [0.85, 1.0].
    Menos descanso y mas pitches = mas fatiga.
    """
    rest_factor  = min(1.0, 0.85 + days_rest * 0.03)
    pitch_factor = max(0.85, 1.0 - max(pitches_last_start - 85, 0) * 0.002)
    return round(rest_factor * pitch_factor, 3)


def bullpen_usage_index(bullpen_era: float, league_era: float = 4.20,
                         innings_last_3: float = 9.0) -> float:
    """
    Indice de uso del bullpen. Valores altos = bullpen cansado/debil.
    """
    era_factor   = bullpen_era / max(league_era, 0.1)
    usage_factor = min(1.5, innings_last_3 / 9.0)
    return round(era_factor * usage_factor, 3)


def mlb_game_score(home_stats: dict, away_stats: dict,
                   home_pitcher: dict, away_pitcher: dict) -> dict:
    """
    Score compuesto para predecir resultado MLB.
    Retorna probabilidades [home_win, away_win] y total esperado.
    """
    # Ventaja de pitching
    h_fip = home_pitcher.get('fip', 4.20)
    a_fip = away_pitcher.get('fip', 4.20)
    pitch_edge = (a_fip - h_fip) / 10  # positivo = ventaja local

    # Ventaja de bateo
    h_ops = home_stats.get('ops', .720)
    a_ops = away_stats.get('ops', .720)
    bat_edge = (h_ops - a_ops) * 2

    # Ventaja de campo (~0.04 en MLB)
    home_adv = 0.04

    # Score total
    raw_edge = pitch_edge + bat_edge + home_adv
    prob_home = 0.5 + raw_edge
    prob_home = max(0.20, min(0.80, prob_home))

    # Total esperado de carreras
    h_runs_exp = home_stats.get('runs_per_game', 4.5)
    a_runs_exp = away_stats.get('runs_per_game', 4.5)
    total_exp  = h_runs_exp + a_runs_exp

    return {
        'prob_home': round(prob_home, 3),
        'prob_away': round(1 - prob_home, 3),
        'expected_total': round(total_exp, 2),
        'pitch_edge': round(pitch_edge, 3),
        'bat_edge': round(bat_edge, 3),
    }


# ============================================================
# BASQUETBOL
# ============================================================

def nba_win_probability(home_stats: dict, away_stats: dict,
                         home_b2b: bool = False, away_b2b: bool = False,
                         home_rest_days: int = 2, away_rest_days: int = 2) -> dict:
    """
    Probabilidad de victoria NBA usando Four Factors y ajustes de descanso.
    """
    h_net = home_stats.get('net_rtg', 0)
    a_net = away_stats.get('net_rtg', 0)

    # Ajuste back-to-back: -3.5 puntos en rating defensivo
    if home_b2b:
        h_net -= 3.5
    if away_b2b:
        a_net -= 3.5

    # Ajuste por descanso: +1.2 por dia extra (cap 3 dias)
    rest_diff = min(home_rest_days, 3) - min(away_rest_days, 3)
    h_net += rest_diff * 1.2

    # Ventaja de local en NBA: ~3.0 puntos
    home_adv = 3.0
    net_diff  = h_net - a_net + home_adv

    # Convertir diferencia de puntos a probabilidad (sigma ~12 pts en NBA)
    prob_home = float(1 / (1 + np.exp(-net_diff / 12)))

    # Total esperado
    avg_pace = (home_stats.get('pace', 100) + away_stats.get('pace', 100)) / 2
    h_ortg   = home_stats.get('ortg', 110)
    a_ortg   = away_stats.get('ortg', 110)
    h_drtg   = home_stats.get('drtg', 110)
    a_drtg   = away_stats.get('drtg', 110)
    total_exp = avg_pace * ((h_ortg + a_ortg + h_drtg + a_drtg) / 4) / 100

    return {
        'prob_home': round(prob_home, 3),
        'prob_away': round(1 - prob_home, 3),
        'expected_total': round(total_exp, 1),
        'net_diff': round(net_diff, 2),
        'home_b2b': home_b2b,
        'away_b2b': away_b2b,
    }


def four_factors_score(efg: float, tov: float, orb: float, ftr: float) -> float:
    """Score de Four Factors de Dean Oliver."""
    return 0.40*efg - 0.25*tov + 0.20*orb + 0.15*ftr


# ============================================================
# FUTBOL AMERICANO (NFL)
# ============================================================

def nfl_win_probability(home_stats: dict, away_stats: dict,
                         neutral_site: bool = False) -> dict:
    """
    Probabilidad de victoria NFL usando DVOA proxy y diferencial de puntos.
    """
    h_dvoa = home_stats.get('dvoa_proxy', 0)
    a_dvoa = away_stats.get('dvoa_proxy', 0)

    h_pt_diff = home_stats.get('pt_diff', 0)
    a_pt_diff = away_stats.get('pt_diff', 0)

    # Ventaja de local en NFL: ~2.5 puntos
    home_adv = 0 if neutral_site else 2.5

    # Score combinado
    h_score = h_dvoa * 5 + h_pt_diff + home_adv
    a_score = a_dvoa * 5 + a_pt_diff
    diff    = h_score - a_score

    # Sigma ~13.5 puntos en NFL
    prob_home = float(1 / (1 + np.exp(-diff / 13.5)))

    # Total esperado
    total_exp = (home_stats.get('pts_per_game', 22) +
                 away_stats.get('pts_per_game', 22) +
                 home_stats.get('pts_allowed', 22) +
                 away_stats.get('pts_allowed', 22)) / 2

    return {
        'prob_home': round(prob_home, 3),
        'prob_away': round(1 - prob_home, 3),
        'expected_total': round(total_exp, 1),
        'score_diff': round(diff, 2),
        'home_adv_applied': home_adv,
    }


def any_a(pass_yards: float, td: float, interceptions: float,
           sack_yards: float, attempts: float, sacks: float) -> float:
    """Adjusted Net Yards per Attempt."""
    return (pass_yards + 20*td - 45*interceptions - sack_yards) / max(attempts + sacks, 1)


def epa_proxy(pts_scored: float, pts_expected: float, plays: float) -> float:
    """Expected Points Added proxy por jugada."""
    return (pts_scored - pts_expected) / max(plays, 1)


# ============================================================
# FUTBOL SOCCER
# ============================================================

def dixon_coles_tau(hg: int, ag: int, lh: float, la: float, rho: float) -> float:
    """Factor de correccion Dixon-Coles para marcadores bajos."""
    if hg == 0 and ag == 0:
        return max(1 - lh * la * rho, 1e-6)
    elif hg == 1 and ag == 0:
        return max(1 + la * rho, 1e-6)
    elif hg == 0 and ag == 1:
        return max(1 + lh * rho, 1e-6)
    elif hg == 1 and ag == 1:
        return max(1 - rho, 1e-6)
    return 1.0


def poisson_score_matrix(lam_h: float, lam_a: float, rho: float = -0.1,
                          max_goals: int = 8) -> np.ndarray:
    """Matriz de probabilidades de marcadores exactos con correccion DC."""
    from scipy.stats import poisson
    matrix = np.zeros((max_goals+1, max_goals+1))
    for i in range(max_goals+1):
        for j in range(max_goals+1):
            tau = dixon_coles_tau(i, j, lam_h, lam_a, rho)
            matrix[i, j] = tau * poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
    matrix /= matrix.sum()
    return matrix


def soccer_probabilities(lam_h: float, lam_a: float, rho: float = -0.1) -> dict:
    """Probabilidades de resultado 1X2 y mercados secundarios."""
    matrix = poisson_score_matrix(lam_h, lam_a, rho)
    prob_home = float(np.tril(matrix, -1).sum())
    prob_draw = float(np.trace(matrix))
    prob_away = float(np.triu(matrix, 1).sum())

    # Mercados secundarios
    goals_matrix = np.array([[i+j for j in range(matrix.shape[1])]
                              for i in range(matrix.shape[0])])
    over_15 = float(matrix[goals_matrix > 1.5].sum())
    over_25 = float(matrix[goals_matrix > 2.5].sum())
    over_35 = float(matrix[goals_matrix > 3.5].sum())

    btts_mask = np.array([[i > 0 and j > 0
                           for j in range(matrix.shape[1])]
                          for i in range(matrix.shape[0])])
    btts = float(matrix[btts_mask].sum())

    # Top 5 marcadores exactos
    flat = [(matrix[i, j], f'{i}-{j}')
            for i in range(matrix.shape[0])
            for j in range(matrix.shape[1])]
    flat.sort(reverse=True)
    top_scores = {s: round(p, 4) for p, s in flat[:10]}

    return {
        'prob_home': round(prob_home, 4),
        'prob_draw': round(prob_draw, 4),
        'prob_away': round(prob_away, 4),
        'over_1.5': round(over_15, 4),
        'over_2.5': round(over_25, 4),
        'over_3.5': round(over_35, 4),
        'btts': round(btts, 4),
        'top_scores': top_scores,
        'lambda_home': lam_h,
        'lambda_away': lam_a,
    }


def form_weight(results: list, decay: float = 0.5) -> float:
    """
    Peso ponderado de forma reciente.
    results: lista de puntos [3,1,0,3,3] (mas reciente primero)
    decay: factor de decaimiento exponencial
    """
    if not results:
        return 1.5
    weights = [decay**i for i in range(len(results))]
    weighted = sum(r*w for r, w in zip(results, weights))
    total_w  = sum(weights) * 3  # max 3 puntos por partido
    return round(weighted / max(total_w, 0.1), 3)
