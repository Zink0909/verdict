"""Known-answer synthetic data generators.

These are the harness's positive/negative controls: before any verdict is
issued, the machinery must (1) find nothing in pure noise, (2) detect a planted
linear signal with both linear and RFF models, (3) detect a planted nonlinear
signal with RFF but not with a linear model, and (4) support Nagel's two
counterfactual experiments (reversal world, wild bootstrap).
"""
from __future__ import annotations

import numpy as np


def pure_noise(n: int, k: int = 5, seed: int = 0, rho: float = 0.95):
    """Persistent predictors with NO predictive content + iid returns.

    Predictors are AR(1) with coefficient rho (matching the persistence of
    typical Goyal-Welch variables); returns are independent noise.
    Returns (X, r) with r[t] the return to be predicted by X[t] (no relation).
    """
    rng = np.random.default_rng(seed)
    X = np.zeros((n, k))
    e = rng.standard_normal((n, k)) * np.sqrt(1 - rho ** 2)
    for t in range(1, n):
        X[t] = rho * X[t - 1] + e[t]
    r = rng.standard_normal(n) * 0.04
    return X, r


def planted_linear(n: int, k: int = 3, snr: float = 0.35, seed: int = 0,
                   rho: float = 0.9):
    """Returns with a genuine linear signal: r[t] = b'X[t] + eps."""
    rng = np.random.default_rng(seed)
    X = np.zeros((n, k))
    e = rng.standard_normal((n, k)) * np.sqrt(1 - rho ** 2)
    for t in range(1, n):
        X[t] = rho * X[t - 1] + e[t]
    b = rng.standard_normal(k)
    signal = X @ b
    signal = signal / signal.std() * snr * 0.04
    r = signal + rng.standard_normal(n) * 0.04
    return X, r


def planted_nonlinear(n: int, seed: int = 0, rho: float = 0.9, snr: float = 0.6):
    """Even-function signal: linearly invisible, RFF-visible.

    r[t] = a*cos(2*x[t]) + eps with x symmetric AR(1): corr(x, cos(2x)) ~ 0,
    so a linear model sees nothing while a Fourier basis captures it.
    """
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    e = rng.standard_normal(n) * np.sqrt(1 - rho ** 2)
    for t in range(1, n):
        x[t] = rho * x[t - 1] + e[t]
    f = np.cos(2 * x)
    f = (f - f.mean()) / f.std() * snr * 0.04
    r = f + rng.standard_normal(n) * 0.04
    return x.reshape(-1, 1), r


def reversal_world(returns, theta1: float = -0.8, theta2: float = -0.4,
                   scale: float = 1.0, seed: int = 0):
    """Nagel's counterfactual: add a simulated MA(2) component with strong
    negative autocorrelation to real returns, creating reversal dynamics.

    Default (theta1, theta2) gives lag-1 autocorrelation ~ -0.27 for the added
    component; exact values are a pinned default (deviation note: Nagel's paper
    parameters to be confirmed at M3 against the original).
    """
    r = np.asarray(returns, dtype=float)
    rng = np.random.default_rng(seed)
    sigma_u = r.std() * scale
    u = rng.standard_normal(len(r) + 2) * sigma_u
    ma = u[2:] + theta1 * u[1:-1] + theta2 * u[:-2]
    return r + ma


def wild_bootstrap_predictors(X, seed: int = 0):
    """Destroy predictive content, preserve persistence and heteroskedasticity.

    Fit AR(1) per predictor, flip innovation signs with a common Rademacher
    draw per time period (common draw preserves cross-sectional dependence),
    rebuild recursively. Deviation note: exact scheme to be confirmed against
    Nagel's appendix at M3.
    """
    X = np.asarray(X, dtype=float)
    n, k = X.shape
    rng = np.random.default_rng(seed)
    out = np.zeros_like(X)
    eta = rng.choice([-1.0, 1.0], size=n)
    for j in range(k):
        x = X[:, j]
        xl, xc = x[:-1], x[1:]
        denom = (xl * xl).sum()
        phi = (xl * xc).sum() / denom if denom > 0 else 0.0
        resid = xc - phi * xl
        out[0, j] = x[0]
        for t in range(1, n):
            out[t, j] = phi * out[t - 1, j] + eta[t] * resid[t - 1]
    return out
