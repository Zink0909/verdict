"""Black-Scholes pricing, Greeks, implied volatility, and P&L attribution.

Two distinct uses, and the distinction matters for what may be concluded:

1. **Never for the verdict.** Valuations and costs behind any headline number
   come from real option-chain snapshots. Model prices are for cross-checks and
   for decomposition only — a modelled price must not carry a conclusion about
   whether an edge exists.
2. **For mechanism.** `pnl_attribution` splits a trade's P&L into delta, vega
   and theta, which is how the buy-the-dip case established that the loss was
   the option expression (premium paid into elevated implied volatility, then
   decay and mean reversion) rather than the underlying view.

Provenance: buy_the_dip/buythedip/options.py.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def bs_price(S, K, T, r, sigma, call: bool = True) -> float:
    """European Black-Scholes price. T in years, sigma annualized, r continuous."""
    if T <= 0:
        return max(S - K, 0.0) if call else max(K - S, 0.0)
    if sigma <= 0:
        fwd = S - K * np.exp(-r * T)
        return max(fwd, 0.0) if call else max(-fwd, 0.0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if call:
        return float(S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))
    return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1))


def bs_greeks(S, K, T, r, sigma, call: bool = True) -> dict:
    """delta, gamma, vega (per 1.00 of IV), theta (per year)."""
    if T <= 0 or sigma <= 0:
        intrinsic_delta = (1.0 if S > K else 0.0) if call else (-1.0 if S < K else 0.0)
        return {"delta": intrinsic_delta, "gamma": 0.0, "vega": 0.0, "theta": 0.0}
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    pdf = norm.pdf(d1)
    delta = norm.cdf(d1) if call else norm.cdf(d1) - 1.0
    gamma = pdf / (S * sigma * np.sqrt(T))
    vega = S * pdf * np.sqrt(T)
    if call:
        theta = -S * pdf * sigma / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
    else:
        theta = -S * pdf * sigma / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
    return {"delta": float(delta), "gamma": float(gamma),
            "vega": float(vega), "theta": float(theta)}


def implied_vol(price, S, K, T, r, call: bool = True) -> float:
    """Invert Black-Scholes for implied volatility; NaN if it cannot be solved."""
    if T <= 0 or price <= 0:
        return float("nan")
    intrinsic = max(S - K, 0.0) if call else max(K - S, 0.0)
    if price < intrinsic - 1e-6:
        return float("nan")
    try:
        return float(brentq(lambda s: bs_price(S, K, T, r, s, call) - price,
                            1e-4, 5.0, maxiter=200))
    except (ValueError, RuntimeError):
        return float("nan")


def iv_is_trustworthy(iv: float, dte: float, delta: float) -> bool:
    """Is this implied-volatility observation usable for decomposition?

    Near expiry and deep in the money the inversion is numerically unstable, so
    those observations are dropped rather than quietly averaged in.
    """
    return bool(dte >= 14 and 0.05 <= delta <= 0.90 and 0.03 < iv < 2.0)


def pnl_attribution(S0, S1, iv0, iv1, K, T0, dt_years, r, call: bool = True) -> dict:
    """Decompose an option's price change into delta / vega / theta / residual.

    A negative vega term is implied volatility mean-reverting against a position
    bought when it was elevated — the second headwind that makes a long call a
    worse expression of a dip thesis than the underlying itself.
    """
    T1 = max(T0 - dt_years, 0.0)
    p0 = bs_price(S0, K, T0, r, iv0, call)
    p1 = bs_price(S1, K, T1, r, iv1, call)
    g = bs_greeks(S0, K, T0, r, iv0, call)
    d_delta = g["delta"] * (S1 - S0)
    d_vega = g["vega"] * (iv1 - iv0)
    d_theta = g["theta"] * dt_years
    total = p1 - p0
    return {"total": total, "delta": d_delta, "vega": d_vega, "theta": d_theta,
            "residual": total - d_delta - d_vega - d_theta, "p0": p0, "p1": p1}
