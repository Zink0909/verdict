#!/usr/bin/env python3
"""verdict minimal regression (offline, seconds). All pass -> exit 0.

Known-answer gates. Every component that can carry a number into a verdict has
one, and several are positive controls: the harness must be able to *find* an
effect that is really there, otherwise a null proves nothing.

  framework/core      compile, ridge-vs-sklearn, ridgeless-minnorm, kernel-equiv
  synthetic controls  noise-finds-nothing, linear-detected, nonlinear-rff-only
  inference           cw-dm-sanity, spanning-known, auc, auc-bootstrap-band
  splits              time-order, no-shuffle-api, sealed-holdout-ledger, walk-forward
  point-in-time       persistence-screen, universe-asof, audits-catch-planted-leak
  costs               turnover-identity, sensitivity-monotone, iv-scaled-spread,
                      budget-position, breakeven-friction
  options             parity-and-greeks, iv-roundtrip, pnl-attribution
  robustness          sweep-and-stability, untested-additions, conclusion-stability
  diagnosis           expression-vs-underlying, kernel-recovers-rff, false-positive,
                      cost-anatomy, drift-detects-planted, attribution-split
  reporting           requires-limitations, embeds-figures, registry-card-states
  agent (layer B)     schema-requires-kill-criteria, tools-are-strict,
                      guardrail-refuses-tuning, number-audit, pipeline-offline,
                      pipeline-catches-planted-number, provider-coverage,
                      data-gated-state, eval-scoring
  platform            case-result-manifests, repository-integrity-audit
  site                index-covers-registry
  app (front end)     form-validation, pages-render
  case: tsmom         controls (common / idio / tilt / noise)
"""
import json
import os
import py_compile
import sys
import tempfile
import traceback

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from verdict import costs as C          # noqa: E402
from verdict import diagnose as DG      # noqa: E402
from verdict import evaluate as E       # noqa: E402
from verdict import features as F       # noqa: E402
from verdict import options as O        # noqa: E402
from verdict import pointintime as PIT  # noqa: E402
from verdict import report as RP        # noqa: E402
from verdict import robust as R         # noqa: E402
from verdict import splits as SP        # noqa: E402
from verdict import synthetic as S      # noqa: E402

RESULTS = []


def check(name, fn):
    try:
        fn(); RESULTS.append((name, True)); print(f"  PASS  {name}")
    except Exception:
        RESULTS.append((name, False)); print(f"  FAIL  {name}\n{traceback.format_exc()}")


# ---------------------------------------------------------------- core ----

def t_compile():
    bad = []
    for dp, _, files in os.walk(ROOT):
        if any(x in dp for x in ("__pycache__", "/.git", "/data")):
            continue
        for f in files:
            if f.endswith(".py"):
                try:
                    py_compile.compile(os.path.join(dp, f), doraise=True)
                except py_compile.PyCompileError as e:
                    bad.append(str(e))
    assert not bad, "\n".join(bad)


def t_ridge_vs_sklearn():
    from sklearn.linear_model import Ridge
    rng = np.random.default_rng(0)
    X, y = rng.standard_normal((40, 60)), rng.standard_normal(40)
    for z in (0.1, 10.0):
        ours = F.ridge_path(X, y, [z], scale_by_T=True)[0]
        sk = Ridge(alpha=z * 40, fit_intercept=False, solver="svd").fit(X, y).coef_
        assert np.allclose(ours, sk, atol=1e-8), f"z={z} mismatch"


def t_ridgeless_minnorm():
    rng = np.random.default_rng(1)
    X, y = rng.standard_normal((12, 200)), rng.standard_normal(12)
    ours = F.ridge_path(X, y, [0.0])[0]
    pinv = np.linalg.pinv(X) @ y
    assert np.allclose(ours, pinv, atol=1e-8)


def t_kernel_equiv():
    rng = np.random.default_rng(2)
    x1, x2 = rng.standard_normal(5), rng.standard_normal(5)
    gamma, P = 1.0, 200_000
    Phi = F.rff(np.vstack([x1, x2]), P, gamma=gamma, seed=3)
    emp = (2.0 / P) * float(Phi[0] @ Phi[1])
    true = float(np.exp(-gamma ** 2 * ((x1 - x2) ** 2).sum() / 2))
    assert abs(emp - true) < 0.02, f"empirical {emp:.4f} vs kernel {true:.4f}"


def _run_strategy(X, r, T=60, P=600, z=1e2, seed=0):
    """Helper: standardize, RFF, rolling forecasts, timing strategy returns."""
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-12)
    Phi = F.rff(Xs, P, gamma=2.0, seed=seed)
    fc = F.rolling_forecasts(Phi, r, T, [z])[0]
    return fc, F.timing_strategy(fc, r)


# ------------------------------------------------- synthetic controls ----

def t_noise_finds_nothing():
    srs = []
    for seed in range(3):
        X, r = S.pure_noise(480, seed=seed)
        _, strat = _run_strategy(X, r, seed=seed)
        srs.append(E.sharpe(pd.Series(strat)))
    assert abs(np.nanmean(srs)) < 0.45, f"noise SR {srs}"


def t_linear_detected():
    X, r = S.planted_linear(480, seed=4)
    Xs = (X - X.mean(0)) / X.std(0)
    fc_lin = F.rolling_forecasts(Xs, r, 60, [1e-3])[0]
    r2_lin = E.oos_r2(r, fc_lin)
    fc_rff, _ = _run_strategy(X, r, z=1e1, seed=4)
    r2_rff = E.oos_r2(r, fc_rff)
    assert r2_lin > 0.01, f"linear misses planted linear ({r2_lin:.4f})"
    assert r2_rff > 0.01, f"RFF misses planted linear ({r2_rff:.4f})"


def t_nonlinear_rff_only():
    X, r = S.planted_nonlinear(600, seed=5)
    Xs = (X - X.mean(0)) / X.std(0)
    fc_lin = F.rolling_forecasts(Xs, r, 120, [1e-3])[0]
    fc_rff, _ = _run_strategy(X, r, T=120, P=400, z=1e0, seed=5)
    r2_lin = E.oos_r2(r, fc_lin)
    r2_rff = E.oos_r2(r, fc_rff)
    assert r2_rff > r2_lin + 0.02 and r2_rff > 0.02, \
        f"RFF should beat linear on even signal (rff {r2_rff:.4f} lin {r2_lin:.4f})"


# ------------------------------------------------------------ inference ----

def t_cw_dm_sanity():
    X, r = S.planted_linear(600, seed=6)
    Xs = (X - X.mean(0)) / X.std(0)
    fc = F.rolling_forecasts(Xs, r, 60, [1e-3])[0]
    mask = ~np.isnan(fc)
    zero = np.zeros(mask.sum())
    cw = E.clark_west(r[mask], zero, fc[mask])
    assert cw["cw_t"] > 1.645, f"CW should detect nested improvement ({cw['cw_t']:.2f})"
    dm = E.diebold_mariano(r[mask], fc[mask], fc[mask])
    assert abs(dm["dm_t"]) < 1e-9 or np.isnan(dm["dm_t"]), "DM on identical forecasts"


def t_spanning_known():
    rng = np.random.default_rng(7)
    n = 240
    idx = pd.date_range("2000-01-31", periods=n, freq="ME")
    factor = pd.Series(rng.normal(0.01, 0.04, n), index=idx)
    y = 1.2 * factor + rng.normal(0, 0.004, n)
    res = E.spanning(y, pd.DataFrame({"F": factor}))
    assert abs(res["alpha_t"]) < 2.0 and res["beta_t"]["F"] > 5.0


# --------------------------------------------------------------- splits ----

def t_splits_time_order():
    dates = pd.date_range("2010-01-31", periods=180, freq="ME")
    sp = SP.time_splits(dates, "2016-12-31", "2019-12-31")
    SP.assert_no_leakage(sp)
    assert sp.sizes == {"train": 84, "valid": 36, "holdout": 60}, sp.sizes
    assert dates[sp.train].max() <= sp.train_end < dates[sp.valid].min()
    assert dates[sp.valid].max() <= sp.valid_end < dates[sp.holdout].min()
    for bad in [("2019-12-31", "2016-12-31"), ("2019-12-31", "2019-12-31")]:
        try:
            SP.time_splits(dates, *bad)
            raise AssertionError(f"bad boundaries accepted: {bad}")
        except ValueError:
            pass
    try:
        SP.time_splits(dates[::-1], "2016-12-31", "2019-12-31")
        raise AssertionError("unsorted dates were accepted")
    except ValueError:
        pass


def t_splits_no_shuffle_api():
    """The discipline is structural: there is no random-split API to misuse."""
    import inspect
    import re
    src = inspect.getsource(SP)
    body = re.sub(r'""".*?"""', "", src, flags=re.S)      # prose may name what code must not do
    for banned in ("shuffle(", "train_test_split(", "KFold(", "permutation(", "sample("):
        assert banned not in body, f"splits module calls {banned}"
    assert not [n for n in dir(SP) if "random" in n.lower() or "shuffle" in n.lower()]


def t_sealed_holdout_ledger():
    with tempfile.TemporaryDirectory() as d:
        ledger = os.path.join(d, "unseal_ledger.json")
        h = SP.SealedHoldout("holdout-2020", ledger)
        assert h.is_sealed and "still sealed" in h.summary()
        cfg = {"model": "cnn", "seeds": 3, "cost_bps": 10}
        rec = h.unseal("final evaluation", cfg)
        assert rec["kind"] == "first-unseal" and not h.is_sealed
        rec2 = h.unseal("re-run for reproduction", dict(cfg))
        assert rec2["kind"] == "reproduction", rec2
        assert len(h.records()) == 2 and "1 identical re-run" in h.summary()
        try:
            h.unseal("just one more look", {**cfg, "seeds": 5})
            raise AssertionError("holdout re-opened under a changed configuration")
        except SP.HoldoutAlreadyUnsealed:
            pass
        # a different holdout in the same ledger is independent
        other = SP.SealedHoldout("holdout-2024", ledger)
        assert other.is_sealed


def t_walk_forward():
    dates = pd.date_range("2010-01-31", periods=120, freq="ME")
    folds = SP.walk_forward(dates, n_folds=4, min_train=60)
    assert len(folds) == 4
    sizes = []
    for f in folds:
        assert f.train.max() < f.test.min(), "walk-forward fold leaks the future"
        sizes.append(len(f.train))
    assert sizes == sorted(sizes) and sizes[-1] > sizes[0], "expanding window not growing"
    assert sum(len(f.test) for f in folds) == 60
    rolling = SP.walk_forward(dates, n_folds=4, min_train=60, expanding=False)
    assert {len(f.train) for f in rolling} == {60}, "rolling window not fixed-length"


# ------------------------------------------------------- point-in-time ----

def t_pit_persistence_screen():
    steady_margin = [0.60] * 8
    # a dip in two of eight years must not revoke a persistent franchise
    dipped = [0.20] * 6 + [0.09, 0.02]
    assert PIT.persistent_quality(dipped, steady_margin)
    # four good years out of eight is not persistence
    weak = [0.20] * 4 + [0.05] * 4
    assert not PIT.persistent_quality(weak, steady_margin)
    # a volatile margin fails the pricing-power leg even with high returns
    assert not PIT.persistent_quality([0.20] * 8, [0.6, 0.2] * 4)
    # short history is never guessed at
    assert not PIT.persistent_quality([0.30] * 5, [0.60] * 5)


def t_pit_universe_asof():
    rows = []
    for tk, disclosure_years in (("EARLY", range(2015, 2023)), ("LATE", range(2019, 2027))):
        for i, y in enumerate(disclosure_years):
            rows.append({"ticker": tk, "fiscal_year": 2015 + i, "roic": 0.2,
                         "gross_margin": 0.6, "asof": f"{y}-06-30"})
    panel = pd.DataFrame(rows)
    screen = lambda g: PIT.persistent_quality(g["roic"], g["gross_margin"])  # noqa: E731
    at_2023 = PIT.universe_asof(panel, "2023-01-01", screen, order_col="fiscal_year")
    assert at_2023 == ["EARLY"], at_2023          # LATE's history is not yet disclosed
    at_2027 = PIT.universe_asof(panel, "2027-01-01", screen, order_col="fiscal_year")
    assert at_2027 == ["EARLY", "LATE"], at_2027


def t_pit_audits_catch_planted_leak():
    clean = pd.DataFrame({"feature_asof": ["2020-01-31", "2020-02-29"],
                          "label_start": ["2020-02-01", "2020-03-01"]})
    assert PIT.audit_signal_timing(clean) == []
    leaky = pd.DataFrame({"feature_asof": ["2020-02-15", "2020-02-29"],
                          "label_start": ["2020-02-01", "2020-03-01"]})
    assert len(PIT.audit_signal_timing(leaky)) == 1
    membership = pd.DataFrame({"date": ["2020-01-31"] * 2, "ticker": ["AAA", "BBB"]})
    ok = pd.DataFrame({"date": ["2020-01-15"], "ticker": ["AAA"]})
    assert PIT.audit_universe_membership(ok, membership) == []
    ghost = pd.DataFrame({"date": ["2020-01-15"], "ticker": ["ZZZ"]})
    assert len(PIT.audit_universe_membership(ghost, membership)) == 1
    fundamentals = pd.DataFrame({"period_end": ["2020-12-31", "2020-12-31"],
                                 "asof": ["2021-02-20", "2020-12-31"]})
    assert len(PIT.audit_disclosure_lag(fundamentals, min_days=30)) == 1
    assert len(PIT.audit_no_future_rows(fundamentals, "2021-01-01", "asof")) == 1


# ---------------------------------------------------------------- costs ----

def t_costs_turnover_identity():
    w = pd.Series({"A": 0.5, "B": -0.5})
    assert C.turnover(w, w) == 0.0
    assert abs(C.turnover(pd.Series({"A": 1.0, "B": -1.0}),
                          pd.Series({"A": -1.0, "B": 1.0})) - 2.0) < 1e-12
    # entering a book from cash is one-way turnover of 1.0
    assert abs(C.turnover(pd.Series(dtype=float), pd.Series({"A": 0.5, "B": -0.5})) - 0.5) < 1e-12


def t_costs_sensitivity_monotone():
    rng = np.random.default_rng(21)
    gross = pd.Series(rng.normal(0.01, 0.04, 240))
    tab = C.cost_sensitivity(gross, 1.0, bps_grid=(0, 5, 10, 20))
    assert list(tab["mean_per_period"]) == sorted(tab["mean_per_period"], reverse=True)
    assert list(tab["sharpe"]) == sorted(tab["sharpe"], reverse=True)
    assert abs(C.net_return(0.01, 1.0, 10) - (0.01 - 0.002)) < 1e-12
    assert abs(C.breakeven_cost_bps(0.01, 1.0) - 50.0) < 1e-9
    assert C.breakeven_cost_bps(0.01, 0.0) == float("inf")


def t_costs_iv_scaled_spread():
    assert abs(C.iv_scaled_spread(0.30) - 0.05) < 1e-12
    assert abs(C.iv_scaled_spread(0.60) - 0.10) < 1e-12       # doubling IV doubles the spread
    assert abs(C.iv_scaled_spread(3.0) - 0.30) < 1e-12        # capped
    assert C.iv_scaled_spread(float("nan")) == 0.05
    assert C.iv_scaled_spread(0.60) > C.iv_scaled_spread(0.30) > 0


def t_costs_budget_position():
    n, invested = C.budget_position(5.0, budget=10_000, multiplier=100)
    assert (n, invested) == (20, 10_000.0)
    n, pnl, ret = C.budget_pnl(5.0, 7.0, budget=10_000)
    assert n == 20 and abs(pnl - 4000.0) < 1e-9 and abs(ret - 0.4) < 1e-12
    # a contract too expensive for the budget is not silently fractionalized
    n, pnl, ret = C.budget_pnl(200.0, 300.0, budget=10_000)
    assert n == 0 and pnl == 0.0 and np.isnan(ret)


# -------------------------------------------------------------- options ----

def t_options_parity_and_greeks():
    S0, K, T, r, sig = 100.0, 95.0, 0.5, 0.02, 0.35
    call = O.bs_price(S0, K, T, r, sig, True)
    put = O.bs_price(S0, K, T, r, sig, False)
    parity = S0 - K * np.exp(-r * T)
    assert abs((call - put) - parity) < 1e-9, "put-call parity violated"
    g = O.bs_greeks(S0, K, T, r, sig, True)
    assert 0 < g["delta"] < 1 and g["gamma"] > 0 and g["vega"] > 0 and g["theta"] < 0
    gp = O.bs_greeks(S0, K, T, r, sig, False)
    assert -1 < gp["delta"] < 0 and abs(gp["gamma"] - g["gamma"]) < 1e-9
    assert O.iv_is_trustworthy(0.3, 30, 0.4)
    assert not O.iv_is_trustworthy(0.3, 5, 0.4)      # too close to expiry
    assert not O.iv_is_trustworthy(0.3, 30, 0.95)    # too deep in the money


def t_options_iv_roundtrip():
    S0, K, T, r, sig = 120.0, 110.0, 0.4, 0.01, 0.42
    px = O.bs_price(S0, K, T, r, sig, True)
    assert abs(O.implied_vol(px, S0, K, T, r, True) - sig) < 1e-6
    assert np.isnan(O.implied_vol(-1.0, S0, K, T, r, True))


def t_options_pnl_attribution():
    a = O.pnl_attribution(S0=100, S1=100.5, iv0=0.40, iv1=0.39, K=100,
                          T0=0.5, dt_years=0.005, r=0.02)
    assert abs(a["residual"]) < 0.05 * abs(a["total"]), a
    assert a["vega"] < 0 and a["theta"] < 0, "falling IV and elapsed time must both cost"
    b = O.pnl_attribution(S0=100, S1=100.5, iv0=0.40, iv1=0.41, K=100,
                          T0=0.5, dt_years=0.005, r=0.02)
    assert b["vega"] > 0 and b["total"] > a["total"]


# ----------------------------------------------------------- robustness ----

def t_robust_sweep_and_stability():
    df = R.sweep({"a": [1, 2, 3], "b": [10, 20]}, lambda a, b: {"prod": a * b})
    assert len(df) == 6 and set(df.columns) == {"a", "b", "prod"}
    assert df["prod"].tolist() == [10, 20, 20, 40, 30, 60]
    same = R.membership_stability(["A", "B"], ["A", "B"])
    assert same["jaccard"] == 1.0 and same["n_added"] == same["n_dropped"] == 0
    moved = R.membership_stability(["A", "B"], ["B", "C"])
    assert moved["added"] == ["C"] and moved["dropped"] == ["A"]
    assert abs(moved["jaccard"] - 1 / 3) < 1e-12


def t_robust_untested_additions():
    added = [(2020, "XYZ"), (2021, "XYZ"), (2020, "AAPL")]
    assert R.untested_additions(added, tested=["AAPL", "MSFT"]) == ["XYZ"]
    assert R.untested_additions([], tested=["AAPL"]) == []


def t_robust_conclusion_stability():
    res = pd.DataFrame([
        {"label": "base", "mean_pnl": -263.0, "win": 0.36},
        {"label": "tighter", "mean_pnl": -180.0, "win": 0.38},
        {"label": "flipped", "mean_pnl": +120.0, "win": 0.41},
    ])
    out = R.conclusion_stability(res, ["mean_pnl", "win"], base_label="base")
    assert out.set_index("label").loc["tighter", "all_agree"]
    assert not out.set_index("label").loc["flipped", "all_agree"]
    try:
        R.conclusion_stability(res, ["mean_pnl"], base_label="absent")
        raise AssertionError("missing base row accepted")
    except ValueError:
        pass


# ------------------------------------------------------------ diagnosis ----

def t_expression_vs_underlying():
    """diagnose.expression_vs_underlying: same-budget stock P&L from S_in/S_out,
    drag = derivative - stock (from the buy-the-dip playbook)."""
    df = pd.DataFrame({"S_in": [100, 100, 100, 100],
                       "S_out": [110, 90, 105, 95],       # stock +10/-10/+5/-5%
                       "dollar_pnl": [500, -1000, -200, -1000]})
    r = DG.expression_vs_underlying(df, budget=10000)
    assert r["n"] == 4
    assert abs(r["underlying_mean"] - 0.0) < 1e-6         # 10k*(0.1-0.1+0.05-0.05)/4
    assert abs(r["deriv_mean"] - (-425.0)) < 1e-6
    assert r["expression_drag"] < 0                        # derivative drags
    # NaN row skipped
    df2 = pd.concat([df, pd.DataFrame({"S_in": [100], "S_out": [np.nan],
                                       "dollar_pnl": [0]})], ignore_index=True)
    assert DG.expression_vs_underlying(df2)["n"] == 4


def t_diagnose_kernel_recovers_rff():
    """diagnose.kernel_ridgeless_forecast must match RFF ridgeless on the same
    data (the mechanism check itself), and expose recency/vol-timing structure."""
    rng = np.random.default_rng(11)
    n, k = 200, 4
    X = np.zeros((n, k)); e = rng.standard_normal((n, k)) * np.sqrt(1 - 0.9 ** 2)
    for t in range(1, n):
        X[t] = 0.9 * X[t - 1] + e[t]
    Xs = (X - X.mean(0)) / X.std(0)
    r = rng.standard_normal(n) * 0.04
    ker = DG.kernel_ridgeless_forecast(Xs, r, T=24, gamma=2.0)
    Phi = F.rff(Xs, 40000, gamma=2.0, seed=0)
    rff_fc = F.rolling_forecasts(Phi, r, 24, [0.0])[0]
    m = ~np.isnan(rff_fc) & ~np.isnan(ker["forecast"])
    corr = np.corrcoef(rff_fc[m], ker["forecast"][m])[0, 1]
    assert corr > 0.9, f"kernel should recover RFF ridgeless (corr {corr:.3f})"
    assert ker["weight_by_lag"].shape == (24,)


def t_diagnose_false_positive():
    """The chart-cnn shape: promising on validation, gone on the sealed block."""
    d = DG.false_positive({"alpha": 0.0068, "alpha_t": 2.41},
                          {"alpha": -0.0029, "alpha_t": -0.62})
    assert d["verdict"] == "false positive caught by the sealed holdout"
    assert d["sign_flip"] and d["validation_significant"] and not d["holdout_significant"]
    assert d["alpha_decay"] < 0
    survived = DG.false_positive({"alpha": 0.006, "alpha_t": 2.6},
                                 {"alpha": 0.005, "alpha_t": 2.2})
    assert survived["verdict"] == "survived out of sample"
    quiet = DG.false_positive({"alpha": 0.001, "alpha_t": 0.4},
                              {"alpha": 0.0005, "alpha_t": 0.2})
    assert quiet["verdict"] == "no claim in either block"


def t_diagnose_cost_anatomy():
    """Alive gross, and the cost at which it dies (chart-cnn validation block)."""
    d = DG.cost_anatomy(gross_mean=0.0071, turn=1.84, realistic_bps=10.0)
    assert abs(d["breakeven_cost_bps"] - 19.293478) < 1e-4, d["breakeven_cost_bps"]
    assert abs(d["net_mean"] - 0.00342) < 1e-9
    assert d["survives_costs"] and 0 < d["cost_share_of_gross"] < 1
    dead = DG.cost_anatomy(gross_mean=0.0071, turn=1.84, realistic_bps=25.0)
    assert not dead["survives_costs"]


# ------------------------------------------------------------ reporting ----

def t_report_requires_limitations():
    v = RP.VerdictReport(title="T", claim="C", verdict="V",
                         sections=[("Setup", "body")], honest_limitations=[])
    try:
        v.render_markdown()
        raise AssertionError("a verdict without limitations was rendered")
    except ValueError:
        pass
    v.honest_limitations = ["  "]          # whitespace is not a limitation
    try:
        v.render_markdown()
        raise AssertionError("blank limitations accepted")
    except ValueError:
        pass
    v.honest_limitations = ["The deep-panic sample is small."]
    md = v.render_markdown()
    for expected in ("# T", "**Claim audited.** C", "**Verdict.** V",
                     "## Setup", "## Honest limitations", "- The deep-panic"):
        assert expected in md, expected


def t_registry_card_states():
    with tempfile.TemporaryDirectory() as d:
        card = {"id": "demo-claim", "state": "not-a-state", "claim": {"source": "X"}}
        for bad, exc in ((card, ValueError),
                         ({**card, "state": "verdict-delivered"}, ValueError)):
            try:
                RP.write_card(bad, d)
                raise AssertionError(f"invalid card accepted: {bad['state']}")
            except exc:
                pass
        good = {"id": "demo-claim", "state": "verdict-delivered",
                "claim": {"source": "Author (2024)", "claimed_effect": "effect"},
                "verdict": {"outcome": "negative", "honest_limitations": ["small sample"]}}
        p = RP.write_card(good, d)
        assert json.loads(p.read_text())["id"] == "demo-claim"
        index = (RP.Path(d) / "README.md").read_text()
        assert "demo-claim" in index and "verdict-delivered" in index
        gated = {"id": "gated-claim", "state": "protocol-ready-data-gated",
                 "claim": {"source": "Author (2020)", "claimed_effect": "other effect"},
                 "why_not_adjudicated": {"blocker": "source corpus is not assembled"}}
        RP.write_card(gated, d)
        index = (RP.Path(d) / "README.md").read_text()
        assert "not adjudicable" in index and index.count("|") > 10


def t_report_embeds_figures():
    """A published verdict must carry its figures inside it.

    Image paths are relative to the document; pandoc resolves them against the
    working directory unless told otherwise, which silently dropped every figure
    until `--resource-path` was passed. Skipped (not failed) without pandoc.
    """
    import base64
    import shutil
    if shutil.which("pandoc") is None:
        print("       (pandoc absent — rendering gate skipped)")
        return
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAE"
        "hQGAhKmMIQAAAABJRU5ErkJggg==")
    with tempfile.TemporaryDirectory() as d:
        doc = RP.Path(d) / "doc"
        (doc / "results").mkdir(parents=True)
        (doc / "results" / "f.png").write_bytes(png)
        v = RP.VerdictReport(title="T", claim="C", verdict="V",
                             sections=[("S", "![fig](results/f.png)")],
                             honest_limitations=["a real limitation"])
        v.write(doc / "report.md")                       # renders HTML too
        html = (doc / "report.html").read_text()
        assert "data:image/png;base64" in html, "figure not embedded in the HTML"
        assert 'src="results/' not in html, "HTML still points at an external file"


# ------------------------------------------------------- discrimination ----

def t_evaluate_auc():
    """Known answers, ties included, cross-checked against sklearn."""
    assert E.auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0        # perfect ranking
    assert E.auc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0        # perfectly inverted
    assert E.auc([0, 1, 0, 1], [0.5] * 4) == 0.5                   # all ties -> chance
    assert np.isnan(E.auc([1, 1, 1], [0.1, 0.2, 0.3]))             # one class -> undefined
    rng = np.random.default_rng(31)
    y = rng.integers(0, 2, 400)
    sc = y * 0.4 + rng.standard_normal(400)                        # partial separation
    from sklearn.metrics import roc_auc_score
    assert abs(E.auc(y, sc) - roc_auc_score(y, sc)) < 1e-12
    # a binary score with heavy ties must still match sklearn's tie handling
    b = (sc > 0).astype(float)
    assert abs(E.auc(y, b) - roc_auc_score(y, b)) < 1e-12


def t_evaluate_auc_bootstrap_band():
    rng = np.random.default_rng(32)
    y = rng.integers(0, 2, 300)
    sc = y * 0.6 + rng.standard_normal(300)
    point = E.auc(y, sc)
    lo, hi = E.block_bootstrap_auc_ci(y, sc, n_boot=200, block=10, seed=1)
    assert lo < point < hi, f"band {lo:.3f}-{hi:.3f} excludes point {point:.3f}"
    assert hi - lo > 0.01, "band implausibly tight"
    assert all(np.isnan(v) for v in E.block_bootstrap_auc_ci([1, 1, 1], [1, 2, 3]))


# --------------------------------------------------------------- drift ----

def _drift_stream(n_signal, n_noise, seed=0):
    """A stream that discriminates, then stops discriminating."""
    rng = np.random.default_rng(seed)
    n = n_signal + n_noise
    y = rng.integers(0, 2, n)
    score = np.empty(n, dtype=float)
    score[:n_signal] = y[:n_signal] * 1.2 + rng.standard_normal(n_signal)   # AUC ~ 0.8
    score[n_signal:] = rng.standard_normal(n_noise)                          # AUC ~ 0.5
    return pd.DataFrame({"date": pd.date_range("2015-01-01", periods=n, freq="B"),
                         "p": score, "y": y})


def t_diagnose_drift_detects_planted():
    """A planted decay must be detected, dated, and flagged BEFORE the trough.

    Note what is deliberately not asserted: that the alarm falls after the
    planted change-point. On a noisy in-control stretch the CUSUM can fire on an
    ordinary dip (here the signal region's AUC has a standard deviation of ~0.05),
    and that early-firing behaviour is a documented property of the detector
    rather than something to paper over. The guarantee that matters for a monitor
    is the one tested: it fires, and it fires before the damage is at its worst.
    """
    d = _drift_stream(400, 300, seed=5)
    rep = DG.drift(d, "date", "p", "y", window=100, baseline_n=40)
    sm = rep["summary"]
    assert sm["n_alarms"] >= 1, "planted drift went undetected"
    first = pd.Timestamp(sm["first_alarm"])
    assert first < pd.Timestamp(sm["worst_auc_date"]), "alarm did not precede the trough"
    assert pd.Timestamp(sm["worst_auc_date"]) > d["date"].iloc[400], \
        "the trough should land after the planted change-point"
    assert sm["baseline_auc"] > sm["worst_auc"] + 0.1, "decay not visible in the metric"
    stable = _drift_stream(700, 0, seed=6)
    assert DG.drift(stable, "date", "p", "y", window=100,
                    baseline_n=40)["summary"]["n_alarms"] == 0, "false alarm on a stable stream"


def t_diagnose_attribution_split():
    """A real driver keeps its sign across the split; a coincident one flips."""
    idx = pd.date_range("2016-01-01", periods=400, freq="B")
    metric = pd.Series(np.linspace(0.62, 0.44, 400), index=idx)      # steady decay
    real = pd.Series(np.linspace(0.0, 1.0, 400), index=idx)          # tracks it throughout
    r = DG.attribution_holds_up(metric, real, split_at=idx[200])
    assert not r["sign_flips_after_split"] and r["corr_full"] < -0.9
    recover = metric.copy()
    recover.iloc[200:] = np.linspace(0.44, 0.60, 200)                # decay then recovery
    r2 = DG.attribution_holds_up(recover, real, split_at=idx[200])
    assert r2["sign_flips_after_split"], r2
    assert r2["corr_full"] < 0 < r2["corr_after"]
    assert "does not explain" in r2["verdict"]


def t_costs_breakeven_friction():
    """Interpolate a measured sensitivity curve to its zero crossing."""
    be = C.breakeven_friction([0.0, 0.05, 0.10, 0.20], [59.0, 17.1, -9.4, -56.2])
    assert abs(be - (0.05 + 0.05 * 17.1 / 26.5)) < 1e-9, be
    assert 0.08 < be < 0.083
    assert np.isnan(C.breakeven_friction([0, 1, 2], [5.0, 4.0, 3.0]))   # never crosses
    assert C.breakeven_friction([0, 1], [10.0, -10.0]) == 0.5


# ---------------------------------------------------------------- agent ----

def t_agent_schema_requires_kill_criteria():
    """A protocol with no kill criteria is a plan to find something, not a test."""
    from verdict.agent.schema import ClaimCard, Protocol
    good = {"data_requirements": ["x"], "splits": "chronological", "benchmarks": ["b"],
            "cost_model": "bps on turnover", "diagnostics": ["d"], "robustness": ["r"],
            "kill_criteria": ["alpha t below 2 on the sealed block"], "rationale": "because"}
    assert Protocol.from_dict(good).preregistered
    for bad, why in (({**good, "kill_criteria": []}, "empty"),
                     ({**good, "kill_criteria": ["   "]}, "whitespace"),
                     ({k: v for k, v in good.items() if k != "benchmarks"}, "missing field")):
        try:
            Protocol.from_dict(bad)
            raise AssertionError(f"accepted a protocol with {why} kill criteria/fields")
        except ValueError:
            pass
    card = {"signal": "s", "universe": "u", "frequency": "monthly", "claimed_effect": "e",
            "sample": "1926-2020", "source": "Author (2024)", "data_needs": ["d"]}
    assert ClaimCard.from_dict(card).source == "Author (2024)"
    try:
        ClaimCard.from_dict({**card, "signal": ""})
        raise AssertionError("accepted a claim card with no signal")
    except ValueError:
        pass


def t_agent_tools_are_strict():
    """Tool schemas are closed, and the dispatcher rejects what the API would not."""
    from verdict.agent import tools as AT
    for d in AT.definitions():
        schema = d["input_schema"]
        assert d.get("strict") is True, f"{d['name']} is not strict"
        assert schema["additionalProperties"] is False, f"{d['name']} allows extra properties"
        assert set(schema["required"]) == set(schema["properties"]), \
            f"{d['name']} has optional properties; strict tools require all of them"
        assert len(d["description"]) > 80, f"{d['name']} description is too thin to route on"
    try:
        AT.run_tool("no_such_tool", {})
        raise AssertionError("dispatched an unknown tool")
    except KeyError:
        pass
    try:
        AT.run_tool("describe_dataset", {"limit": 5})
        raise AssertionError("accepted an invented argument")
    except TypeError:
        pass
    nums = AT.collect_numbers([{"a": 1.5, "b": {"c": [2, 3]}, "flag": True, "s": "x"}])
    assert sorted(nums) == [1.5, 2.0, 3.0], nums     # booleans are not numbers


def t_agent_guardrail_refuses_tuning():
    """Post-hoc tuning is refused with the clause it violates; research talk is not."""
    from verdict.agent import guardrails as G
    for request in ["Tune the shrinkage until the alpha is significant.",
                    "Can you adjust the threshold so that the result is positive?",
                    "just peek at the holdout again",
                    "Drop the worst months and rerun.",
                    "skip the costs for now"]:
        try:
            G.check_request(request)
            raise AssertionError(f"allowed a protocol violation: {request!r}")
        except G.ProtocolViolation as e:
            assert "protocol" in str(e).lower() and "refused" in str(e).lower()
    for benign in ["Run the protocol as written.",
                   "What does the kernel-equivalence diagnostic show?",
                   "Report the Sharpe ratio and its confidence interval.",
                   "The costs should be charged at 10 bps as specified."]:
        assert G.check_request(benign, raise_on_violation=False) is None, benign


def t_agent_number_audit():
    """Prose may not invent numbers; rounding and percent forms are allowed."""
    from verdict.agent import guardrails as G
    allowed = [0.3593, -0.0855, 12000.0]
    clean = G.audit_numbers("Sharpe 0.36 fell to -0.09 with 12,000 features.", allowed)
    assert clean["clean"], clean
    assert G.audit_numbers("A share of 36% of draws.", allowed)["clean"]      # percent form
    dirty = G.audit_numbers("It returned 18.4 percent in the 1970s.", allowed)
    assert not dirty["clean"] and 18.4 in dirty["unsupported"], dirty
    ctx = G.audit_numbers("The sample starts in 1926.", allowed,
                          context='{"sample": "1926-2020"}')
    assert ctx["clean"], "numbers from the audited claim are allowed"
    assert not G.audit_numbers("Sharpe was 0.9.", allowed)["clean"]           # not a rounding


def _fast_agent_run(plant_error=False, data_available=True):
    """A minimal scripted transcript — small feature count so the gate stays seconds."""
    from verdict.agent import pipeline
    from verdict.agent.demo import CLAIM, PROTOCOL
    from verdict.agent.llm import Reply, ScriptedModel

    def write(system, messages, tools_, schema, effort):
        import json as _json
        results = _json.loads(messages[-1]["content"].split("Results:\n", 1)[1]
                              .split("\n\nWrite the verdict.")[0])
        r = results[-1]["result"]
        text = (f"The strategy reached a Sharpe of {r['sharpe_annualized']} on "
                f"{r['n_out_of_sample']} out-of-sample months. Honest limitations: one "
                f"configuration, {r['seeds']} seeds.")
        if plant_error:
            text += " It also returned 41.7 percent in the 1990s."
        return Reply(text=text)

    model = ScriptedModel([
        ScriptedModel.json_reply(CLAIM),
        ScriptedModel.json_reply(PROTOCOL),
        ScriptedModel.tool_reply("run_complex_model",
                                 {"n_features": 20, "window": 12, "shrinkage": 0.001, "seeds": 1}),
        Reply(text="Done."),
        write,
    ])
    return pipeline.run_audit(model, "paper text", data_available=data_available,
                              approve=lambda _claim, _protocol: True,
                              case_id="complexity-voc")


def t_agent_pipeline_offline():
    """The whole loop, offline: real numbers, and the audit passes on honest prose."""
    run = _fast_agent_run()
    assert run.state == "verdict-delivered", run.state
    assert run.approved and run.claim and run.protocol
    calls = [s for s in run.tool_trace if "tool" in s]
    assert len(calls) == 1 and calls[0]["tool"] == "run_complex_model"
    assert "sharpe_annualized" in calls[0]["result"], "the tool returned no number"
    assert run.number_audit["clean"], run.number_audit
    assert run.verdict_text and "Honest limitations" in run.verdict_text


def t_agent_pipeline_catches_planted_number():
    """A figure the model invented is flagged rather than published."""
    run = _fast_agent_run(plant_error=True)
    assert not run.number_audit["clean"]
    assert run.state == "draft-withheld", run.state
    assert 41.7 in run.number_audit["unsupported"], run.number_audit
    assert any("unsupported" in n for n in run.notes), run.notes


def t_agent_requires_explicit_approval():
    """No callback means no human approval, so no analysis may execute."""
    from verdict.agent import pipeline
    from verdict.agent.demo import PAPER_STAND_IN, scripted_model
    run = pipeline.run_audit(scripted_model(), PAPER_STAND_IN, case_id="complexity-voc")
    assert not run.approved and run.state == "in-progress"
    assert run.tool_trace == [] and run.verdict_text == ""


def t_agent_rejects_data_gated_case():
    """A registered but unexecuted case must never acquire a tool provider."""
    from verdict.agent import providers
    try:
        providers.get_provider("lazy-prices-10k-changes")
        raise AssertionError("data-gated case acquired an execution provider")
    except ValueError as exc:
        assert "data-gated" in str(exc)


def t_agent_providers_cover_delivered_cases():
    """Every delivered case has an honest case-scoped provider and no others do."""
    from verdict.agent import providers
    from verdict.catalog import CASES

    delivered = {case.card_id for case in CASES if case.role != "data-gated"}
    assert set(providers.supported_case_ids()) == delivered
    for spec in CASES:
        if spec.role == "data-gated":
            continue
        provider = providers.get_provider(spec.card_id)
        assert provider.mode == spec.agent_mode
        names = {item["name"] for item in provider.definitions()}
        assert names
        if provider.mode == "evidence-readonly":
            assert names == {"describe_case_evidence", "read_case_result"}
            description = provider.run_tool("describe_case_evidence", {})
            assert description["execution_mode"] == "evidence-readonly"
            document, sections = next(iter(description["documents"].items()))
            evidence = provider.run_tool(
                "read_case_result", {"document": document, "section": sections[0]})
            assert evidence["case_id"] == spec.card_id and "value" in evidence


def t_agent_data_gated_state():
    """No data means a registered protocol and no verdict — the honest third outcome."""
    run = _fast_agent_run(data_available=False)
    assert run.state == "protocol-ready-data-gated"
    assert run.protocol is not None and run.tool_trace == [] and run.verdict_text == ""


def t_agent_eval_scoring():
    """Coverage, and — the point — the omissions listed individually."""
    from verdict.agent import evals
    checklist = [
        {"id": "a", "label": "A", "source": "expert", "any_of": ["kernel", "smoother"]},
        {"id": "b", "label": "B", "source": "expert", "any_of": ["bootstrap"]},
        {"id": "c", "label": "C", "source": "practice", "any_of": ["cost", "friction"]},
    ]
    score = evals.score_protocol(
        ["charge realistic costs against turnover", "check the kernel equivalence"], checklist)
    assert score["n_covered"] == 2 and score["coverage"] == round(2 / 3, 4)
    assert [m["id"] for m in score["missed"]] == ["b"]
    assert score["by_source"]["expert"]["covered"] == 1
    assert score["by_source"]["practice"]["coverage"] == 1.0
    empty = evals.score_protocol([], checklist)
    assert empty["n_covered"] == 0 and len(empty["missed"]) == 3
    report = evals.render_report(score, "T", "provenance line")
    for expected in ("# T", "Missed", "Honest limitations", "provenance line"):
        assert expected in report, expected


# ------------------------------------------------------------------ site ----

def t_site_index_covers_registry():
    """The front page is generated from the cards, so it cannot omit or invent one."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import build_site

    cards = build_site.load_cards()
    assert cards, "no registry cards found"
    links = {c["id"]: f"cases/{c['id']}.html" for c in cards
             if c["state"] == "verdict-delivered"}
    page = build_site.build_index(cards, links)
    for c in cards:
        title = c.get("title") or c["id"]
        assert title in page, f"front page omits {title!r}"
        if c["state"] == "verdict-delivered":
            assert links[c["id"]] in page, f"{c['id']} has a verdict but no link"
        if c["state"] == "protocol-ready-data-gated":
            assert "data-gated" in page and "no verdict is issued" in page
            assert not (c.get("verdict") or {}).get("outcome"), \
                "a data-gated card must not carry a verdict"
    # delivered counter is derived, not typed
    delivered = sum(1 for c in cards if c["state"] == "verdict-delivered")
    assert f"{delivered} adjudicated so far" in page
    # positioning language stays out of the harness's own vocabulary
    lede = page.split('<p class="lede">')[1].split("</p>")[0]
    for jargon in ("Sharpe", "alpha", "backtest"):
        assert jargon.lower() not in lede.lower(), f"positioning language uses {jargon!r}"


def t_case_catalog_is_complete():
    """One inventory must cover every card and keep four foundations explicit."""
    from verdict.catalog import CASE_BY_ID, FOUNDATIONAL_CASES
    card_ids = {p.stem for p in RP.Path(ROOT, "registry").glob("*.json")}
    assert card_ids == set(CASE_BY_ID), (card_ids ^ set(CASE_BY_ID))
    assert len(FOUNDATIONAL_CASES) == 4
    for case in FOUNDATIONAL_CASES:
        assert RP.Path(ROOT, "cases", case.folder).is_dir(), case


def t_case_result_manifests():
    """Every delivered case has the same normalized, content-addressed envelope."""
    from pathlib import Path
    from verdict.case_contract import CaseResult, load_case_result
    from verdict.catalog import CASES

    root = Path(ROOT)
    for spec in CASES:
        if spec.role == "data-gated":
            continue
        card = json.loads((root / "registry" / f"{spec.card_id}.json").read_text())
        actual = load_case_result(root / "cases" / spec.folder / "case_result.json")
        expected = CaseResult.build(spec, root, card["state"]).to_dict()
        assert actual == expected, f"stale case_result.json for {spec.card_id}"
        assert actual["artifacts"] and all(a["sha256"] for a in actual["artifacts"])


def t_repository_integrity_audit():
    """The cross-layer audit must close the card → artifact → site → agent chain."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import audit_integrity

    result = audit_integrity.audit(RP.Path(ROOT))
    assert result["ok"], "\n".join(result["errors"])


# ------------------------------------------------------------------- app ----

def t_app_form_validation():
    """The form is held to the same standard as everything else — especially the
    one field a form is most tempted to make optional."""
    from verdict.schema_help import CLAIM_FIELDS, PROTOCOL_FIELDS, build_card, normalize
    claim = {"signal": "a rule", "universe": "u", "frequency": "monthly",
             "claimed_effect": "an effect", "sample": "1990-2020", "source": "Author (2024)",
             "data_needs": "prices\nreturns"}
    proto = {"data_requirements": "point-in-time prices", "splits": "chronological",
             "benchmarks": "zero\nmomentum", "cost_model": "10bps on turnover",
             "diagnostics": "mechanism check", "robustness": "seeds",
             "kill_criteria": "alpha t below 2 on the sealed block", "rationale": "because"}
    card = build_card(claim, proto, "demo-claim", "A demo", data_available=True)
    assert card["state"] == "in-progress" and card["verdict"] is None
    assert card["claim"]["data_needs"] == ["prices", "returns"]        # lines -> list
    assert normalize(claim, CLAIM_FIELDS)["signal"] == "a rule"
    assert len(normalize(proto, PROTOCOL_FIELDS)["benchmarks"]) == 2

    gated = build_card(claim, proto, "demo-claim", "A demo", False, "the corpus is not built")
    assert gated["state"] == "protocol-ready-data-gated"
    assert gated["why_not_adjudicated"]["blocker"]

    for bad, why in (((claim, {**proto, "kill_criteria": "  "}, "x-y", "T", True, ""),
                      "no kill criteria"),
                     ((claim, proto, "Bad_ID", "T", True, ""), "an unusable id"),
                     ((claim, proto, "x-y", "", True, ""), "no title"),
                     ((claim, proto, "x-y", "T", False, ""), "data-gated with no blocker"),
                     (({**claim, "source": ""}, proto, "x-y", "T", True, ""), "no source")):
        try:
            build_card(*bad)
            raise AssertionError(f"the form accepted a card with {why}")
        except ValueError:
            pass


def t_app_pages_render():
    """Every screen runs. A front end that raises on a page is not a front end."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    for page in ("The register", "New claim", "Evaluate a result", "The agent"):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, (page, [e.value for e in at.exception])
    # the evaluate screen must actually compute when given a series
    at.sidebar.radio[0].set_value("Evaluate a result").run()
    at.radio[0].set_value("Use a synthetic example").run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.metric) >= 3, "the evaluation screen reported no figures"


def t_tsmom_controls():
    """The tsmom case must separate a claim-specific effect from three impostors.

    Two seeds of each world rather than the six the case file runs, to keep this
    suite in seconds; `cases/tsmom/validate.py` is the full version. The point of
    having it here at all is that the positive control travels with the negative
    ones: COMMON must come back clean, or a null this machinery produces later
    carries no information.
    """
    sys.path.insert(0, os.path.join(ROOT, "cases", "tsmom"))
    from validate import synth, CONTROLS   # noqa: E402
    from run import execute                # noqa: E402

    for kind, _blurb, checks in CONTROLS:
        for seed in (0, 1):
            res = execute(*synth(kind, seed=seed), sign_draws=40,
                          seal_from=None, label=f"{kind}-{seed}")
            for name, fn in checks:
                assert fn(res), f"{kind} seed {seed}: {name}"


def t_tsmom_implementation_robustness():
    """Holding, correlation and integer-contract plumbing have known answers."""
    sys.path.insert(0, os.path.join(ROOT, "cases", "tsmom"))
    import decode_panel as DP
    import tsmom as T

    idx = pd.date_range("2020-01-31", periods=30, freq="ME")
    positions = pd.DataFrame({"A": np.arange(30, dtype=float)}, index=idx)
    held = T.holding_period_positions(positions, 3)
    assert np.isnan(held.iloc[1, 0]) and held.iloc[2, 0] == 1.0
    assert T.holding_period_positions(positions, 1).equals(positions)

    x = np.arange(30, dtype=float)
    pair = T.most_correlated_pair(pd.DataFrame({"A": x, "B": 2 * x, "C": (-1) ** x},
                                               index=idx))
    assert set(pair[:2]) == {"A", "B"} and np.isclose(pair[2], 1.0)

    small_idx = pd.date_range("2024-01-31", periods=3, freq="ME")
    desired = pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=small_idx)
    prices = pd.DataFrame({"A": [100.0, 110.0, 99.0]}, index=small_idx)
    adjusted_returns = pd.DataFrame({"A": [np.nan, 0.10, -0.10]}, index=small_idx)
    contracts = T.integer_contract_positions(
        desired, prices, capital=1_000.0, point_values={"A": 10.0})
    assert contracts["A"].tolist() == [1.0, 1.0, 1.0]
    account = T.integer_contract_returns(
        contracts, prices, adjusted_returns, capital=1_000.0,
        point_values={"A": 10.0})
    assert np.allclose(account.to_numpy(), [0.10, -0.11])
    turnover = T.integer_contract_turnover(
        contracts, prices, capital=1_000.0, point_values={"A": 10.0})
    assert np.allclose(turnover.to_numpy(), [1.0, 2.2, 1.98])

    with tempfile.TemporaryDirectory() as tmp:
        panel_path = RP.Path(tmp, "panel.csv")
        panel_path.write_text(
            "date,A_close,A_trade_close,A_v20\n"
            "2024-01-31,100,101,0.2\n"
            "2024-02-29,110,111,0.2\n")
        panel_closes, _ = T.load_panel(panel_path, today="2024-12-31")
        trade_closes = T.load_execution_prices(
            panel_path, panel_closes.columns, today="2024-12-31")
        assert panel_closes.columns.tolist() == ["A"]
        assert trade_closes is not None and trade_closes.columns.tolist() == ["A"]
        assert trade_closes.iloc[-1, 0] == 111.0

        bad_path = RP.Path(tmp, "bad-panel.csv")
        bad_rows = ["date,A_close,A_trade_close,A_v20"]
        for date in pd.date_range("2020-01-31", periods=30, freq="ME"):
            bad_rows.append(f"{date.date()},100,100,0.2")
        bad_payload = "\n".join(bad_rows) + "\n"
        bad_path.write_text(bad_payload)
        for check in (
            lambda: DP.validate_execution_columns(bad_payload),
            lambda: T.load_execution_prices(
                bad_path, ["A"], today="2024-12-31"),
        ):
            try:
                check()
            except ValueError as exc:
                assert "identical" in str(exc)
            else:
                raise AssertionError("adjusted data labelled Raw was accepted")

    result = json.loads(RP.Path(ROOT, "cases", "tsmom", "results.json").read_text())
    axes = {row["axis"] for row in result["robustness"]}
    assert {"holding_period_months", "drop_correlated_markets"}.issubset(axes)
    assert result["integer_contract_sizing"]["status"] == "data-gated"
    assert result["protocol_coverage"]["not_executed"] == [
        "integer-contract and multiplier-aware sizing"]


GATES = [
    ("compile", t_compile),
    ("ridge-vs-sklearn", t_ridge_vs_sklearn),
    ("ridgeless-minnorm", t_ridgeless_minnorm),
    ("kernel-equiv", t_kernel_equiv),
    ("noise-finds-nothing", t_noise_finds_nothing),
    ("linear-detected", t_linear_detected),
    ("nonlinear-rff-only", t_nonlinear_rff_only),
    ("cw-dm-sanity", t_cw_dm_sanity),
    ("spanning-known", t_spanning_known),
    ("evaluate-auc", t_evaluate_auc),
    ("evaluate-auc-bootstrap-band", t_evaluate_auc_bootstrap_band),
    ("splits-time-order", t_splits_time_order),
    ("splits-no-shuffle-api", t_splits_no_shuffle_api),
    ("sealed-holdout-ledger", t_sealed_holdout_ledger),
    ("walk-forward", t_walk_forward),
    ("pit-persistence-screen", t_pit_persistence_screen),
    ("pit-universe-asof", t_pit_universe_asof),
    ("pit-audits-catch-planted-leak", t_pit_audits_catch_planted_leak),
    ("costs-turnover-identity", t_costs_turnover_identity),
    ("costs-sensitivity-monotone", t_costs_sensitivity_monotone),
    ("costs-iv-scaled-spread", t_costs_iv_scaled_spread),
    ("costs-budget-position", t_costs_budget_position),
    ("costs-breakeven-friction", t_costs_breakeven_friction),
    ("options-parity-and-greeks", t_options_parity_and_greeks),
    ("options-iv-roundtrip", t_options_iv_roundtrip),
    ("options-pnl-attribution", t_options_pnl_attribution),
    ("robust-sweep-and-stability", t_robust_sweep_and_stability),
    ("robust-untested-additions", t_robust_untested_additions),
    ("robust-conclusion-stability", t_robust_conclusion_stability),
    ("expression-vs-underlying", t_expression_vs_underlying),
    ("diagnose-kernel-recovers-rff", t_diagnose_kernel_recovers_rff),
    ("diagnose-false-positive", t_diagnose_false_positive),
    ("diagnose-cost-anatomy", t_diagnose_cost_anatomy),
    ("diagnose-drift-detects-planted", t_diagnose_drift_detects_planted),
    ("diagnose-attribution-split", t_diagnose_attribution_split),
    ("report-requires-limitations", t_report_requires_limitations),
    ("report-embeds-figures", t_report_embeds_figures),
    ("registry-card-states", t_registry_card_states),
    ("agent-schema-requires-kill-criteria", t_agent_schema_requires_kill_criteria),
    ("agent-tools-are-strict", t_agent_tools_are_strict),
    ("agent-guardrail-refuses-tuning", t_agent_guardrail_refuses_tuning),
    ("agent-number-audit", t_agent_number_audit),
    ("agent-pipeline-offline", t_agent_pipeline_offline),
    ("agent-pipeline-catches-planted-number", t_agent_pipeline_catches_planted_number),
    ("agent-requires-explicit-approval", t_agent_requires_explicit_approval),
    ("agent-rejects-data-gated-case", t_agent_rejects_data_gated_case),
    ("agent-providers-cover-delivered-cases", t_agent_providers_cover_delivered_cases),
    ("agent-data-gated-state", t_agent_data_gated_state),
    ("agent-eval-scoring", t_agent_eval_scoring),
    ("site-index-covers-registry", t_site_index_covers_registry),
    ("case-catalog-is-complete", t_case_catalog_is_complete),
    ("case-result-manifests", t_case_result_manifests),
    ("repository-integrity-audit", t_repository_integrity_audit),
    ("app-form-validation", t_app_form_validation),
    ("app-pages-render", t_app_pages_render),
    ("tsmom-controls", t_tsmom_controls),
    ("tsmom-implementation-robustness", t_tsmom_implementation_robustness),
]

for nm, fn in GATES:
    check(nm, fn)

n_fail = sum(1 for _, ok in RESULTS if not ok)
print(f"\n{'='*40}\n{len(RESULTS)-n_fail}/{len(RESULTS)} passed")
sys.exit(1 if n_fail else 0)
