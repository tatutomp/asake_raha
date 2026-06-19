"""Volatiliteettianalyysi ja yön-yli-strategian pisteytys.

Strategia
---------
Osta ~20 min ennen Nasdaqin sulkua, pidä yön yli, myy ~20 min avauksen
jälkeen. Etsitään osakkeita jotka
  1) heiluvat paljon (korkea volatiliteetti / ATR),
  2) sulkevat vahvasti (hinta lähellä päivän huippua = momentum sulkuun),
  3) ovat lyhyellä aikavälillä nousussa,
  4) ovat historiallisesti gapanneet ylös yön yli,
  5) joissa on tänään tavallista enemmän vaihtoa.

HUOM: Tämä on opetus- ja analyysityökalu, EI sijoitusneuvonta.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from tickers import NASDAQ_100


# --- Pisteytyksen painot (summa = 1.0) ---
WEIGHTS = {
    "volatility": 0.30,      # ATR% / heiluvuus
    "close_strength": 0.25,  # sulkuhinta lähellä päivän huippua
    "momentum_5d": 0.20,     # 5 päivän tuotto
    "gap_winrate": 0.15,     # historiallinen yön yli -nousuosuus
    "rel_volume": 0.10,      # tämän päivän suhteellinen vaihto
}


@dataclass
class StockMetrics:
    ticker: str
    price: float
    volatility: float        # 20pv päivätuottojen keskihajonta (%)
    atr_pct: float           # ATR(14) / hinta (%)
    momentum_5d: float       # 5pv tuotto (%)
    momentum_20d: float      # 20pv tuotto (%)
    close_strength: float    # (close-low)/(high-low), 0..1
    rel_volume: float        # tämän päivän vaihto / 20pv ka.
    gap_winrate: float       # osuus päivistä joina yön yli -gap > 0 (%)
    avg_gap: float           # keskimääräinen yön yli -gap (%)
    score: float = 0.0       # lopullinen yhdistelmäpiste 0..100

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = round(v, 4)
        return d


def _download(tickers: List[str], period: str = "3mo") -> pd.DataFrame:
    """Lataa päivädatan kaikille tickereille kerralla."""
    df = yf.download(
        tickers,
        period=period,
        interval="1d",
        progress=False,
        auto_adjust=True,
        group_by="ticker",
        threads=True,
    )
    return df


def _ticker_frame(df: pd.DataFrame, ticker: str) -> Optional[pd.DataFrame]:
    """Poimi yhden tickerin OHLCV-data MultiIndex-datasta."""
    try:
        if isinstance(df.columns, pd.MultiIndex):
            sub = df[ticker].copy()
        else:
            sub = df.copy()  # yksi ticker
    except (KeyError, TypeError):
        return None
    if "Close" not in sub.columns:
        return None
    # Pudota rivit joilta puuttuu sulkuhinta (esim. tämän päivän kesken
    # oleva istunto, jolla on jo volyymi mutta ei vielä OHLC-hintoja).
    sub = sub[sub["Close"].notna()]
    if sub.empty:
        return None
    return sub


def _compute_metrics(ticker: str, sub: pd.DataFrame) -> Optional[StockMetrics]:
    close = sub["Close"].dropna()
    if len(close) < 25:
        return None

    high = sub["High"]
    low = sub["Low"]
    openp = sub["Open"]
    vol = sub["Volume"]

    last = close.index[-1]
    price = float(close.iloc[-1])
    if not math.isfinite(price) or price <= 0:
        return None

    # Päivätuottojen volatiliteetti (20pv)
    returns = close.pct_change()
    volatility = float(returns.tail(20).std() * 100)

    # ATR(14)
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]
    atr_pct = float(atr14 / price * 100) if math.isfinite(atr14) else 0.0

    # Momentum
    mom5 = float((price / close.iloc[-6] - 1) * 100) if len(close) >= 6 else 0.0
    mom20 = float((price / close.iloc[-21] - 1) * 100) if len(close) >= 21 else 0.0

    # Sulkuvahvuus: missä sulku osui päivän vaihteluvälillä
    h, l = float(high.iloc[-1]), float(low.iloc[-1])
    close_strength = float((price - l) / (h - l)) if h > l else 0.5

    # Suhteellinen vaihto
    avg_vol = vol.tail(20).mean()
    rel_volume = float(vol.iloc[-1] / avg_vol) if avg_vol and avg_vol > 0 else 1.0

    # Yön yli -gapit: open_t / close_{t-1} - 1
    gaps = (openp / close.shift(1) - 1).dropna().tail(30)
    if len(gaps) > 0:
        gap_winrate = float((gaps > 0).mean() * 100)
        avg_gap = float(gaps.mean() * 100)
    else:
        gap_winrate, avg_gap = 50.0, 0.0

    return StockMetrics(
        ticker=ticker,
        price=price,
        volatility=volatility,
        atr_pct=atr_pct,
        momentum_5d=mom5,
        momentum_20d=mom20,
        close_strength=close_strength,
        rel_volume=rel_volume,
        gap_winrate=gap_winrate,
        avg_gap=avg_gap,
    )


def _percentile_rank(values: np.ndarray) -> np.ndarray:
    """Muunna arvot 0..1 persentiilijärjestykseen (suurempi = parempi)."""
    order = values.argsort().argsort()
    n = len(values)
    if n <= 1:
        return np.zeros(n)
    return order / (n - 1)


def analyze_universe(tickers: Optional[List[str]] = None) -> List[StockMetrics]:
    """Analysoi koko universumi ja palauta pisteytetyt osakkeet."""
    tickers = tickers or NASDAQ_100
    df = _download(tickers)

    metrics: List[StockMetrics] = []
    for t in tickers:
        sub = _ticker_frame(df, t)
        if sub is None:
            continue
        m = _compute_metrics(t, sub)
        if m is not None:
            metrics.append(m)

    if not metrics:
        return []

    # Persentiilipisteytys jokaiselle komponentille
    vol_arr = np.array([m.atr_pct for m in metrics])
    cs_arr = np.array([m.close_strength for m in metrics])
    mom_arr = np.array([m.momentum_5d for m in metrics])
    gap_arr = np.array([m.gap_winrate for m in metrics])
    relv_arr = np.array([min(m.rel_volume, 5.0) for m in metrics])

    p_vol = _percentile_rank(vol_arr)
    p_cs = _percentile_rank(cs_arr)
    p_mom = _percentile_rank(mom_arr)
    p_gap = _percentile_rank(gap_arr)
    p_relv = _percentile_rank(relv_arr)

    for i, m in enumerate(metrics):
        score = (
            WEIGHTS["volatility"] * p_vol[i]
            + WEIGHTS["close_strength"] * p_cs[i]
            + WEIGHTS["momentum_5d"] * p_mom[i]
            + WEIGHTS["gap_winrate"] * p_gap[i]
            + WEIGHTS["rel_volume"] * p_relv[i]
        )
        m.score = round(float(score) * 100, 2)

    metrics.sort(key=lambda x: x.score, reverse=True)
    return metrics


def pick_portfolio(metrics: List[StockMetrics], n: int = 5) -> List[StockMetrics]:
    """Valitse n parasta ostokohdetta."""
    return metrics[:n]


def reason_text(m: StockMetrics) -> str:
    """Lyhyt suomenkielinen perustelu osakkeelle."""
    parts = []
    if m.atr_pct >= 3:
        parts.append(f"korkea volatiliteetti (ATR {m.atr_pct:.1f}%)")
    elif m.atr_pct >= 2:
        parts.append(f"kohtalainen volatiliteetti (ATR {m.atr_pct:.1f}%)")
    if m.close_strength >= 0.7:
        parts.append("sulkee vahvasti lähellä päivän huippua")
    if m.momentum_5d > 0:
        parts.append(f"5pv momentum +{m.momentum_5d:.1f}%")
    if m.gap_winrate >= 55:
        parts.append(f"gappaa ylös {m.gap_winrate:.0f}% öistä")
    if m.rel_volume >= 1.3:
        parts.append(f"vilkas vaihto ({m.rel_volume:.1f}x)")
    return "; ".join(parts) if parts else "yhdistelmäpisteet universumin kärkeä"


# --- Myyntiarvio (avauksen jälkeen) ---

TAKE_PROFIT = 1.5   # %
STOP_LOSS = -1.0    # %


def fetch_current_prices(tickers: List[str]) -> Dict[str, float]:
    """Hae viimeisin saatavilla oleva hinta (proxy avaushinnalle ~20 min jälkeen)."""
    prices: Dict[str, float] = {}
    if not tickers:
        return prices
    df = yf.download(
        tickers,
        period="2d",
        interval="5m",
        progress=False,
        auto_adjust=True,
        group_by="ticker",
        threads=True,
    )
    for t in tickers:
        sub = _ticker_frame(df, t)
        if sub is not None and "Close" in sub.columns:
            series = sub["Close"].dropna()
            if len(series):
                prices[t] = float(series.iloc[-1])
    # Fallback päivädatasta
    missing = [t for t in tickers if t not in prices]
    if missing:
        dfd = yf.download(
            missing, period="2d", interval="1d", progress=False,
            auto_adjust=True, group_by="ticker", threads=True,
        )
        for t in missing:
            sub = _ticker_frame(dfd, t)
            if sub is not None and "Close" in sub.columns:
                series = sub["Close"].dropna()
                if len(series):
                    prices[t] = float(series.iloc[-1])
    return prices


def evaluate_sells(positions: List[dict]) -> List[dict]:
    """Arvioi eilen ostettujen positioiden yön yli -tuotto ja anna myyntisuositus.

    positions: lista dictejä joissa vähintään 'ticker' ja 'buy_price'.
    """
    tickers = [p["ticker"] for p in positions]
    prices = fetch_current_prices(tickers)

    results = []
    for p in positions:
        t = p["ticker"]
        buy = float(p.get("buy_price", 0) or 0)
        cur = prices.get(t)
        if cur is None or buy <= 0:
            results.append({
                **p,
                "current_price": cur,
                "gap_pct": None,
                "decision": "EI DATAA",
                "reason": "Hintaa ei saatu haettua",
            })
            continue
        gap = (cur / buy - 1) * 100
        if gap >= TAKE_PROFIT:
            decision = "MYY (voitto)"
            reason = f"Yön yli +{gap:.2f}% — ota voitto kotiin"
        elif gap <= STOP_LOSS:
            decision = "MYY (stop loss)"
            reason = f"Yön yli {gap:.2f}% — katkaise tappio"
        else:
            decision = "MYY (strategia)"
            reason = (f"Yön yli {gap:+.2f}% — sulje positio strategian "
                      f"mukaisesti avauksen jälkeen")
        results.append({
            **p,
            "current_price": round(cur, 2),
            "gap_pct": round(gap, 2),
            "decision": decision,
            "reason": reason,
        })
    return results
