"""Simulated share prices for when no market data API key is set.

Generates a believable price for a ticker at a moment in time using smooth
value noise. The price is fully determined by the ticker and the timestamp,
so the same inputs always give the same price, and it wanders gently like
a real stock rather than jumping around randomly.
"""

import hashlib
import math
from datetime import datetime, timezone

EPOCH = datetime(2025,1,1, tzinfo=timezone.utc)
SWING = 0.4 ## How far the price wanders from its base level, as a fraction
OCTAVES = 5 ## Layers of noise, from a slow daily trend down to intraday wiggle

def _seed(Ticker: str) -> int:
    """A stable integer derived from the ticker, repeatable across processes"""
    Digest = hashlib.sha256(Ticker.upper().encode()).digest()
    return int.from_bytes(Digest[:8], "big")


def _lattice(Seed: int, n: int) -> float:
    """A repeatable pseudo-random value in [-1,1] at integer point n"""
    Digest = hashlib.sha256(f"{Seed}:{n}".encode()).digest()
    return int.from_bytes(Digest[:4], "big") / 0xFFFFFFFF *2 -1


def _noise(Seed: int, x:float) -> float:
    """Smoothly interpolated noise between the lattice points around x"""
    Low = math.floor(x)
    t = x - Low
    Smooth = t*t*(3-2*t)
    return _lattice(Seed, Low) * (1-Smooth) + _lattice(Seed, Low+1) * Smooth


def _wander(Seed: int, x:float) -> float:
    """Sum several octaves of noise for a natural trend-plus-wiggle shape"""
    Total = 0.0
    Normaliser = 0.0
    Amplitude = 1.0
    Frequency = 1.0
    for _ in range(OCTAVES):
        Total += Amplitude * _noise(Seed, x*Frequency)
        Normaliser += Amplitude
        Amplitude /=2
        Frequency *=2
    return Total/Normaliser

def SimulatedPrice(Ticker: str, When: datetime | None = None) -> float:
    """Return a believable, smoothly varying share price for the ticker"""
    When = When or datetime.now(timezone.utc)
    Seed = _seed(Ticker)
    Base = 20 + Seed % 480
    Days = (When - EPOCH).total_seconds() / 86400
    return round(Base * (1+SWING*_wander(Seed,Days)), 2)
