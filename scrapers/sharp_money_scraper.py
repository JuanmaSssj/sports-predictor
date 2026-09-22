"""
Sharp Money Scraper - Kalshi + Polymarket
Solo lectura: detecta donde esta el dinero institucional real.
NO se usa para apostar, solo para confirmar/contradecir el modelo.
"""
import time
import requests
import numpy as np
from config import KALSHI_BASE, POLYMARKET_CLOB

_cache = {}
CACHE_TTL = 300  # 5 minutos (datos de mercado cambian rapido)


class KalshiAnalyzer:
    """Analiza libro de ordenes de Kalshi para detectar sharp money."""

    def __init__(self, min_notional: float = 3000.0):
        self.min_notional = min_notional

    def get_orderbook(self, ticker: str) -> dict:
        now = time.time()
        if ticker in _cache and now - _cache[ticker]['ts'] < CACHE_TTL:
            return _cache[ticker]['data']
        try:
            url = f'{KALSHI_BASE}/markets/{ticker}/orderbook'
            r = requests.get(url, timeout=8)
            r.raise_for_status()
            data = r.json()
            _cache[ticker] = {'data': data, 'ts': now}
            return data
        except Exception as e:
            print(f'[Kalshi] Error {ticker}: {e}')
            return {}

    def analyze(self, ticker: str) -> dict:
        raw = self.get_orderbook(ticker)
        book = raw.get('orderbook', {})
        yes_levels = book.get('yes', [])
        no_levels  = book.get('no', [])

        yes_notional = sum(p * q * 100 for p, q in yes_levels
                          if p * q * 100 >= self.min_notional)
        no_notional  = sum(p * q * 100 for p, q in no_levels
                          if p * q * 100 >= self.min_notional)
        total = yes_notional + no_notional + 1e-9

        imbalance = (yes_notional - no_notional) / total
        direction = 'YES' if imbalance > 0.1 else ('NO' if imbalance < -0.1 else 'NEUTRAL')

        best_yes = max((p for p, _ in yes_levels), default=0)
        best_no  = max((p for p, _ in no_levels),  default=0)
        midpoint = (best_yes + (1 - best_no)) / 2 if yes_levels and no_levels else 0.5

        return {
            'source':        'Kalshi',
            'ticker':        ticker,
            'direction':     direction,
            'imbalance':     round(imbalance, 4),
            'yes_notional':  round(yes_notional, 0),
            'no_notional':   round(no_notional, 0),
            'total_notional': round(total, 0),
            'midpoint':      round(midpoint, 4),
            'sharp_active':  abs(imbalance) > 0.2 and total > 10000,
        }


class PolymarketAnalyzer:
    """Analiza CLOB de Polymarket para detectar flujo institucional."""

    def __init__(self, min_notional: float = 3000.0):
        self.min_notional = min_notional

    def get_clob(self, token_id: str) -> dict:
        now = time.time()
        key = f'poly_{token_id}'
        if key in _cache and now - _cache[key]['ts'] < CACHE_TTL:
            return _cache[key]['data']
        try:
            url = f'{POLYMARKET_CLOB}/book'
            r = requests.get(url, params={'token_id': token_id}, timeout=8)
            r.raise_for_status()
            data = r.json()
            _cache[key] = {'data': data, 'ts': now}
            return data
        except Exception as e:
            print(f'[Polymarket] Error {token_id}: {e}')
            return {}

    def analyze(self, token_id: str) -> dict:
        clob = self.get_clob(token_id)
        bids = clob.get('bids', [])
        asks = clob.get('asks', [])

        bid_notional = sum(float(o['price']) * float(o['size'])
                          for o in bids
                          if float(o['price']) * float(o['size']) >= self.min_notional)
        ask_notional = sum(float(o['price']) * float(o['size'])
                          for o in asks
                          if float(o['price']) * float(o['size']) >= self.min_notional)
        total = bid_notional + ask_notional + 1e-9

        imbalance = (bid_notional - ask_notional) / total
        direction = 'BUY' if imbalance > 0.1 else ('SELL' if imbalance < -0.1 else 'NEUTRAL')

        best_bid = max((float(o['price']) for o in bids), default=0)
        best_ask = min((float(o['price']) for o in asks), default=1)
        midpoint = (best_bid + best_ask) / 2

        return {
            'source':        'Polymarket',
            'token_id':      token_id,
            'direction':     direction,
            'imbalance':     round(imbalance, 4),
            'bid_notional':  round(bid_notional, 0),
            'ask_notional':  round(ask_notional, 0),
            'total_notional': round(total, 0),
            'midpoint':      round(midpoint, 4),
            'sharp_active':  abs(imbalance) > 0.2 and total > 10000,
        }


class VPINDetector:
    """
    VPIN adaptado a mercados de prediccion binarios.
    Detecta flujo informado (sharp money) via desequilibrio de volumen.
    """

    def __init__(self, bucket_size: float = 10_000.0):
        self.bucket_size = bucket_size
        self.trades: list = []

    def add_trades(self, trades: list[dict]):
        """trades: lista de {'volume': float, 'side': 'buy'|'sell'}"""
        self.trades.extend(trades)

    def compute(self) -> dict:
        if not self.trades:
            return {'vpin': 0, 'direction': 'NEUTRAL', 'interpretation': 'Sin datos'}

        buckets = []
        buy = sell = vol = 0.0
        for t in self.trades:
            v = t['volume']
            s = t['side']
            while v > 0:
                space = self.bucket_size - vol
                fill  = min(v, space)
                if s == 'buy':
                    buy += fill
                else:
                    sell += fill
                vol += fill
                v   -= fill
                if vol >= self.bucket_size:
                    buckets.append((buy, sell))
                    buy = sell = vol = 0.0

        if not buckets:
            return {'vpin': 0, 'direction': 'NEUTRAL', 'interpretation': 'Buckets insuficientes'}

        buys  = np.array([b[0] for b in buckets])
        sells = np.array([b[1] for b in buckets])
        vpin  = float(np.abs(buys - sells).mean() / self.bucket_size)
        dir_v = float((buys - sells).mean())

        z = 0.0
        if len(buckets) > 1:
            imb = np.abs(buys - sells)
            z   = float((imb[-1] - imb.mean()) / (imb.std() + 1e-9))

        if vpin > 0.3 and z > 1.5:
            direction = 'BUY' if dir_v > 0 else 'SELL'
            interp = f'SHARP MONEY ACTIVO EN {direction}'
        elif vpin > 0.2:
            interp = 'FLUJO ELEVADO - MONITOREAR'
            direction = 'BUY' if dir_v > 0 else 'SELL'
        else:
            interp = 'FLUJO NORMAL'
            direction = 'NEUTRAL'

        return {
            'vpin':           round(vpin, 4),
            'directional':    round(dir_v, 2),
            'z_score':        round(z, 3),
            'n_buckets':      len(buckets),
            'direction':      direction,
            'interpretation': interp,
            'sharp_active':   vpin > 0.3 and z > 1.5,
        }


def get_combined_sharp_signal(kalshi_ticker: str = None,
                               poly_token: str = None) -> dict:
    """
    Combina senales de Kalshi y Polymarket en una sola direccion.
    """
    signals = []
    details = []

    if kalshi_ticker:
        k = KalshiAnalyzer().analyze(kalshi_ticker)
        details.append(k)
        if k['sharp_active']:
            signals.append(1 if k['direction'] == 'YES' else -1)

    if poly_token:
        p = PolymarketAnalyzer().analyze(poly_token)
        details.append(p)
        if p['sharp_active']:
            signals.append(1 if p['direction'] == 'BUY' else -1)

    if not signals:
        combined = 'NEUTRAL'
    elif sum(signals) > 0:
        combined = 'SHARP_BUY'
    elif sum(signals) < 0:
        combined = 'SHARP_SELL'
    else:
        combined = 'MIXED'

    return {
        'combined_direction': combined,
        'sharp_active': bool(signals),
        'details': details,
    }
