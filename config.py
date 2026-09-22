import os
from dotenv import load_dotenv

load_dotenv()

ODDS_API_KEY      = os.getenv('ODDS_API_KEY', '')
ODDS_API_BASE     = 'https://api.the-odds-api.com/v4'
MLB_API_BASE      = 'https://statsapi.mlb.com/api/v1'
OPEN_METEO_BASE   = 'https://api.open-meteo.com/v1'
KALSHI_BASE       = 'https://trading-api.kalshi.com/trade-api/v2'
POLYMARKET_CLOB   = 'https://clob.polymarket.com'
CACHE_TIMEOUT     = 1800
TRAINING_INTERVAL = 1800
FLASK_SECRET      = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
