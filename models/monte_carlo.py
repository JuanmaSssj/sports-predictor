"""
Simulacion Monte Carlo con correccion Dixon-Coles.
Usada para todos los deportes con adaptaciones por deporte.
"""
import numpy as np
from scipy.stats import norm
from models.sabermetrics import dixon_coles_tau, poisson_score_matrix


def wilson_ci(p: float, n: int, z: float = 1.96) -> tuple:
    denom  = 1 + z**2 / n
    center = (p + z**2 / (2*n)) / denom
    margin = z * np.sqrt(p*(1-p)/n + z**2/(4*n**2)) / denom
    return round(max(0, center - margin), 4), round(min(1, center + margin), 4)


def monte_carlo_soccer(lam_h: float, lam_a: float, rho: float = -0.1,
                        n: int = 50_000) -> dict:
    """Monte Carlo para futbol soccer con Dixon-Coles."""
    rng = np.random.default_rng(42)
    hg  = rng.poisson(lam_h, n)
    ag  = rng.poisson(lam_a, n)

    weights = np.array([dixon_coles_tau(int(h), int(a), lam_h, lam_a, rho)
                        for h, a in zip(hg, ag)])
    weights = np.maximum(weights, 0)
    weights /= weights.sum()

    ph = float(np.dot(weights, (hg > ag).astype(float)))
    pd = float(np.dot(weights, (hg == ag).astype(float)))
    pa = float(np.dot(weights, (hg < ag).astype(float)))
    tg = hg + ag

    return {
        'prob_home': round(ph, 4), 'prob_draw': round(pd, 4), 'prob_away': round(pa, 4),
        'ci_home': wilson_ci(ph, n), 'ci_draw': wilson_ci(pd, n), 'ci_away': wilson_ci(pa, n),
        'over_1.5': round(float(np.dot(weights, (tg > 1.5).astype(float))), 4),
        'over_2.5': round(float(np.dot(weights, (tg > 2.5).astype(float))), 4),
        'over_3.5': round(float(np.dot(weights, (tg > 3.5).astype(float))), 4),
        'btts':     round(float(np.dot(weights, ((hg > 0) & (ag > 0)).astype(float))), 4),
        'xg_home':  round(float(np.dot(weights, hg)), 2),
        'xg_away':  round(float(np.dot(weights, ag)), 2),
    }


def monte_carlo_totals(mean: float, std: float, line: float,
                        n: int = 50_000) -> dict:
    """
    Monte Carlo para mercados de totales (NBA, NFL, MLB).
    Asume distribucion normal del total de puntos/carreras.
    """
    rng    = np.random.default_rng(42)
    totals = rng.normal(mean, std, n)
    over   = float((totals > line).mean())
    under  = 1 - over
    return {
        'expected_total': round(mean, 2),
        'std': round(std, 2),
        'line': line,
        'over_prob': round(over, 4),
        'under_prob': round(under, 4),
        'ci_over': wilson_ci(over, n),
    }
