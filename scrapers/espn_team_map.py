"""
Mapeo de ESPN team IDs -> MLB Stats API team IDs.
ESPN usa IDs cortos (13, 21) y MLB Stats API usa IDs largos (147, 121).
Fuente de MLB IDs: https://statsapi.mlb.com/api/v1/teams
"""

ESPN_TO_MLB = {
    # AL East
    '2':   110,  # Baltimore Orioles
    '3':   111,  # Boston Red Sox
    '10':  147,  # New York Yankees
    '30':  139,  # Tampa Bay Rays
    '14':  141,  # Toronto Blue Jays
    # AL Central
    '4':   145,  # Chicago White Sox
    '5':   114,  # Cleveland Guardians
    '6':   116,  # Detroit Tigers
    '7':   118,  # Kansas City Royals
    '9':   142,  # Minnesota Twins
    # AL West
    '13':  140,  # Texas Rangers
    '18':  117,  # Houston Astros
    '11':  133,  # Oakland Athletics
    '12':  136,  # Seattle Mariners
    '1':   108,  # Los Angeles Angels
    # NL East
    '15':  144,  # Atlanta Braves
    '28':  146,  # Miami Marlins
    '21':  121,  # New York Mets
    '22':  143,  # Philadelphia Phillies
    '20':  120,  # Washington Nationals
    # NL Central
    '16':  112,  # Chicago Cubs
    '17':  113,  # Cincinnati Reds
    '8':   158,  # Milwaukee Brewers
    '23':  134,  # Pittsburgh Pirates
    '24':  138,  # St. Louis Cardinals
    # NL West
    '29':  109,  # Arizona Diamondbacks
    '27':  115,  # Colorado Rockies
    '19':  119,  # Los Angeles Dodgers
    '25':  135,  # San Diego Padres
    '26':  137,  # San Francisco Giants
}


def espn_to_mlb_id(espn_id: str) -> int | None:
    """Convierte un ESPN team ID a MLB Stats API team ID."""
    return ESPN_TO_MLB.get(str(espn_id))


def mlb_to_espn_id(mlb_id: int) -> str | None:
    """Convierte un MLB Stats API team ID a ESPN team ID."""
    for espn_id, mlb in ESPN_TO_MLB.items():
        if mlb == mlb_id:
            return espn_id
    return None