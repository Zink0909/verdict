"""Random Fourier Features and the full ridge path (KMZ conventions).

Pinned construction (see cases/complexity/M0_PINNED.md):
  - Omega ~ N(0, 1) with shape (K, P/2); A = gamma * X @ Omega;
    features = interleaved [sin(A), cos(A)] -> P columns total (no 1/sqrt(P)
    scaling; the scale is absorbed by the ridge penalty convention).
  - Ridge with NO intercept (this is Buncic's switch (i); expose it as a flag)
    and effective penalty alpha = z * T (T = training-window length).
  - Full z path from one SVD per training window; ridgeless = z -> 0 limit
    (minimum-norm solution via pseudo-inverse).
"""
from __future__ import annotations

import numpy as np


def rff(X: np.ndarray, P: int, gamma: float = 2.0, seed: int = 0) -> np.ndarray:
    """Generate P random Fourier features for X (n_obs, K) -> (n_obs, P).

    Interleaves sin/cos pairs so that truncating columns keeps matched pairs.
    P must be even.
    """
    if P % 2 != 0:
        raise ValueError("P must be even (sin/cos pairs)")
    X = np.asarray(X, dtype=float)
    rng = np.random.default_rng(seed)
    omega = rng.standard_normal((X.shape[1], P // 2))
    A = gamma * (X @ omega)
    S = np.empty((X.shape[0], P), dtype=float)
    S[:, 0::2] = np.sin(A)
    S[:, 1::2] = np.cos(A)
    return S


def ridge_path(X: np.ndarray, y: np.ndarray, z_grid: np.ndarray,
               scale_by_T: bool = True) -> np.ndarray:
    """Ridge coefficients for every z in one SVD. Returns (len(z_grid), P).

    Solves min ||y - X b||^2 + lam ||b||^2 with lam = z*T (KMZ convention,
    scale_by_T=True) or lam = z. No intercept (see module docstring).
    z = 0 entries give the ridgeless minimum-norm solution.
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float).ravel()
    T = X.shape[0]
    U, s, Vt = np.linalg.svd(X, full_matrices=False)
    Uty = U.T @ y
    out = np.empty((len(z_grid), X.shape[1]), dtype=float)
    for i, z in enumerate(np.asarray(z_grid, dtype=float)):
        lam = z * T if scale_by_T else z
        if lam <= 0:
            d = np.divide(1.0, s, out=np.zeros_like(s), where=s > 1e-12)
        else:
            d = s / (s ** 2 + lam)
        out[i] = Vt.T @ (d * Uty)
    return out


def rolling_forecasts(S: np.ndarray, R: np.ndarray, T: int, z_grid: np.ndarray,
                      scale_by_T: bool = True):
    """Rolling one-step-ahead forecasts (KMZ timing setup).

    S: (n, P) feature matrix; R: (n,) next-period target aligned so that
    row t of S predicts R[t] (caller handles the alignment/lag).
    For each t in [T, n): train on rows [t-T, t), predict row t.

    Returns forecasts with shape (len(z_grid), n) — NaN before index T.
    """
    S = np.asarray(S, dtype=float)
    R = np.asarray(R, dtype=float).ravel()
    n = S.shape[0]
    out = np.full((len(z_grid), n), np.nan)
    for t in range(T, n):
        B = ridge_path(S[t - T:t], R[t - T:t], z_grid, scale_by_T=scale_by_T)
        out[:, t] = B @ S[t]
    return out


def timing_strategy(forecasts: np.ndarray, R: np.ndarray) -> np.ndarray:
    """KMZ timing strategy: position proportional to the forecast.

    Strategy return at t = forecast_t * R_t (R aligned as in rolling_forecasts).
    Accepts (n,) or (n_z, n) forecasts; returns the same shape.
    """
    return np.asarray(forecasts) * np.asarray(R, dtype=float)
