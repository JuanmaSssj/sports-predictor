"""
Sabermetricas completas para los 4 deportes.
Probabilidades calibradas con datos reales de cada deporte.
"""
import numpy as np


# ============================================================
# BEISBOL - MLB
# ============================================================

def fip(hr, bb, hbp, k, ip, c_fip=3.10):
    return (13*hr + 3*(bb+hbp) - 2*k) / max(ip, 0.1) + c_fip

def woba(bb, hbp, singles, doubles, triples, hr, pa):
    return (0.696*bb + 0.726*hbp + 0.883*singles + 1.244*doubles +
            1.569*triples + 2.004*hr) / max(pa, 1)

def babip(h, hr, ab, k, sf):
    return (h - hr) / max(ab - k - hr + sf, 1)

def pythagorean_expectation(rs, ra, exp=1.83):
    rs = max(rs, 0.1); ra = max(ra, 0.1)
    return rs**exp / (rs**exp + ra**exp)


def mlb_game_score(home_batting: dict, away_batting: dict,
                   home_pitcher: dict, away_pitcher: dict) -> dict:
    """
    Score MLB usando FIP, OPS, wOBA, forma reciente.
    Ventaja local MLB: ~54% historico.
    """
    # FIP del pitcher (menor = mejor)
    h_fip = home_pitcher.get('fip', 4.20)
    a_fip = away_pitcher.get('fip', 4.20)
    league_avg_fip = 4.20

    # Ventaja de pitching: diferencia normalizada
    pitch_edge = (a_fip - h_fip) / (league_avg_fip * 2)  # rango aprox [-0.5, 0.5]

    # OPS del equipo
    h_ops = home_batting.get('ops', 0.720)
    a_ops = away_batting.get('ops', 0.720)
    league_avg_ops = 0.720
    bat_edge = (h_ops - a_ops) / (league_avg_ops * 0.5)

    # wOBA
    h_woba = home_batting.get('woba', 0.318)
    a_woba = away_batting.get('woba', 0.318)
    woba_edge = (h_woba - a_woba) / 0.060  # 1 std dev wOBA ~0.030

    # Forma reciente (ultimos 10)
    h_l10 = home_batting.get('last10_pct', 0.500)
    a_l10 = away_batting.get('last10_pct', 0.500)
    form_edge = (h_l10 - a_l10) * 0.5

    # Ventaja local MLB
    home_adv = 0.040

    # Score total ponderado
    total_edge = (pitch_edge * 0.40 +
                  bat_edge   * 0.25 +
                  woba_edge  * 0.20 +
                  form_edge  * 0.15 +
                  home_adv)

    # Convertir a probabilidad con sigmoide calibrada para MLB
    # sigma ~0.20 para MLB (menos varianza que otros deportes)
    prob_home = float(1 / (1 + np.exp(-total_edge / 0.20)))
    prob_home = max(0.30, min(0.75, prob_home))  # limitar rango realista

    # Total esperado de carreras
    h_rpg = home_batting.get('runs_per_game', 4.5)
    a_rpg = away_batting.get('runs_per_game', 4.5)
    # Ajuste por FIP del pitcher contrario
    h_exp = h_rpg * (a_fip / league_avg_fip)
    a_exp = a_rpg * (h_fip / league_avg_fip)
    total_exp = h_exp + a_exp

    return {
        'prob_home':      round(prob_home, 4),
        'prob_away':      round(1 - prob_home, 4),
        'expected_total': round(total_exp, 2),
        'pitch_edge':     round(pitch_edge, 3),
        'bat_edge':       round(bat_edge, 3),
        'h_fip':          h_fip,
        'a_fip':          a_fip,
    }


# ============================================================
# BASQUETBOL - NBA
# ============================================================

def nba_win_probability(home_stats: dict, away_stats: dict,
                         home_b2b: bool = False, away_b2b: bool = False,
                         home_rest: int = 2, away_rest: int = 2) -> dict:
    """
    Probabilidad NBA usando NetRtg, Four Factors, descanso, back-to-back.
    Ventaja local NBA: ~3.0 puntos de rating.
    """
    h_net = home_stats.get('net_rtg', 0.0)
    a_net = away_stats.get('net_rtg', 0.0)

    # Four Factors score
    h_ff = four_factors_score(
        home_stats.get('efg_pct', .500),
        home_stats.get('tov_pct', .140),
        home_stats.get('orb_pct', .250),
        home_stats.get('ft_rate', .250),
    )
    a_ff = four_factors_score(
        away_stats.get('efg_pct', .500),
        away_stats.get('tov_pct', .140),
        away_stats.get('orb_pct', .250),
        away_stats.get('ft_rate', .250),
    )
    ff_diff = (h_ff - a_ff) * 20  # escalar a puntos

    # Back-to-back penalty
    b2b_adj = 0
    if home_b2b: b2b_adj -= 3.5
    if away_b2b: b2b_adj += 3.5

    # Descanso
    rest_diff = (min(home_rest, 4) - min(away_rest, 4)) * 1.2

    # Ventaja local
    home_adv = 3.0

    net_diff = h_net - a_net + ff_diff + b2b_adj + rest_diff + home_adv

    # sigma ~11 puntos en NBA
    prob_home = float(1 / (1 + np.exp(-net_diff / 11)))
    prob_home = max(0.25, min(0.80, prob_home))

    # Total esperado
    avg_pace = (home_stats.get('pace', 100) + away_stats.get('pace', 100)) / 2
    h_ortg   = home_stats.get('ortg', 110)
    a_ortg   = away_stats.get('ortg', 110)
    h_drtg   = home_stats.get('drtg', 110)
    a_drtg   = away_stats.get('drtg', 110)
    total_exp = avg_pace * ((h_ortg + a_drtg + a_ortg + h_drtg) / 4) / 100

    return {
        'prob_home':      round(prob_home, 4),
        'prob_away':      round(1 - prob_home, 4),
        'expected_total': round(total_exp, 1),
        'net_diff':       round(net_diff, 2),
        'home_b2b':       home_b2b,
        'away_b2b':       away_b2b,
        'ff_diff':        round(ff_diff, 3),
    }


def four_factors_score(efg, tov, orb, ftr):
    return 0.40*efg - 0.25*tov + 0.20*orb + 0.15*ftr


# ============================================================
# FUTBOL AMERICANO - NFL
# ============================================================

def nfl_win_probability(home_stats: dict, away_stats: dict,
                         neutral: bool = False) -> dict:
    """
    Probabilidad NFL usando DVOA proxy, diferencial de puntos,
    turnover diff, 3rd down, red zone.
    Ventaja local NFL: ~2.5 puntos.
    """
    # Diferencial de puntos por partido
    h_ptd = home_stats.get('pt_diff', 0.0)
    a_ptd = away_stats.get('pt_diff', 0.0)

    # DVOA proxy
    h_dvoa = home_stats.get('dvoa_proxy', 0.0)
    a_dvoa = away_stats.get('dvoa_proxy', 0.0)

    # Turnover differential (cada TO vale ~4 puntos)
    h_to = home_stats.get('to_diff', 0.0)
    a_to = away_stats.get('to_diff', 0.0)
    to_edge = (h_to - a_to) * 0.8

    # 3rd down y red zone
    h_3rd = home_stats.get('third_down_pct', .380)
    a_3rd = away_stats.get('third_down_pct', .380)
    h_rz  = home_stats.get('red_zone_pct', .550)
    a_rz  = away_stats.get('red_zone_pct', .550)
    situational = ((h_3rd - a_3rd) + (h_rz - a_rz)) * 5

    home_adv = 0 if neutral else 2.5

    total_diff = ((h_ptd - a_ptd) * 0.40 +
                  (h_dvoa - a_dvoa) * 5 * 0.30 +
                  to_edge * 0.20 +
                  situational * 0.10 +
                  home_adv)

    # sigma ~13.5 puntos en NFL
    prob_home = float(1 / (1 + np.exp(-total_diff / 13.5)))
    prob_home = max(0.20, min(0.82, prob_home))

    # Total esperado
    total_exp = (home_stats.get('pts_per_game', 22) +
                 away_stats.get('pts_per_game', 22) +
                 home_stats.get('pts_allowed', 22) +
                 away_stats.get('pts_allowed', 22)) / 2

    return {
        'prob_home':      round(prob_home, 4),
        'prob_away':      round(1 - prob_home, 4),
        'expected_total': round(total_exp, 1),
        'score_diff':     round(total_diff, 2),
        'to_edge':        round(to_edge, 2),
    }


# ============================================================
# FUTBOL SOCCER
# ============================================================

def dixon_coles_tau(hg, ag, lh, la, rho):
    if hg == 0 and ag == 0: return max(1 - lh*la*rho, 1e-6)
    elif hg == 1 and ag == 0: return max(1 + la*rho, 1e-6)
    elif hg == 0 and ag == 1: return max(1 + lh*rho, 1e-6)
    elif hg == 1 and ag == 1: return max(1 - rho, 1e-6)
    return 1.0


def poisson_score_matrix(lam_h, lam_a, rho=-0.1, max_goals=8):
    from scipy.stats import poisson
    matrix = np.zeros((max_goals+1, max_goals+1))
    for i in range(max_goals+1):
        for j in range(max_goals+1):
            tau = dixon_coles_tau(i, j, lam_h, lam_a, rho)
            matrix[i, j] = tau * poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a)
    s = matrix.sum()
    return matrix / s if s > 0 else matrix


def soccer_probabilities(lam_h, lam_a, rho=-0.1):
    matrix = poisson_score_matrix(lam_h, lam_a, rho)
    prob_home = float(np.tril(matrix, -1).sum())
    prob_draw = float(np.trace(matrix))
    prob_away = float(np.triu(matrix, 1).sum())

    goals = np.array([[i+j for j in range(matrix.shape[1])]
                       for i in range(matrix.shape[0])])
    over_15 = float(matrix[goals > 1.5].sum())
    over_25 = float(matrix[goals > 2.5].sum())
    over_35 = float(matrix[goals > 3.5].sum())
    btts    = float(matrix[(np.arange(matrix.shape[0])[:,None] > 0) &
                            (np.arange(matrix.shape[1])[None,:] > 0)].sum())

    flat = sorted([(matrix[i,j], f'{i}-{j}')
                   for i in range(matrix.shape[0])
                   for j in range(matrix.shape[1])], reverse=True)
    top_scores = {s: round(p, 4) for p, s in flat[:10]}

    return {
        'prob_home': round(prob_home, 4),
        'prob_draw': round(prob_draw, 4),
        'prob_away': round(prob_away, 4),
        'over_1.5':  round(over_15, 4),
        'over_2.5':  round(over_25, 4),
        'over_3.5':  round(over_35, 4),
        'btts':      round(btts, 4),
        'top_scores': top_scores,
        'lambda_home': lam_h,
        'lambda_away': lam_a,
    }


def form_weight(results: list, decay=0.5):
    if not results: return 1.5
    weights = [decay**i for i in range(len(results))]
    return round(sum(r*w for r,w in zip(results,weights)) / max(sum(weights)*3, 0.1), 3)
