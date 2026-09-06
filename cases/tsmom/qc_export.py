# QuantConnect *Research* notebook — print the minimal panel the TSMOM protocol needs.
# ---------------------------------------------------------------------------
# Free tier cannot download files, so this prints a gzip+base64 blob to paste back.
# It follows the same pattern as cta_trend/qc/print_sleeve_returns_qc.py, but exports
# the PER-MARKET panel rather than an aggregate return series: the pre-registered
# protocol needs per-market data for every one of its benchmarks, and an aggregate
# sleeve series cannot produce any of them.
#
# What it prints, at month-end only (small enough to paste):
#     date, <SYM>_close, <SYM>_trade_close, <SYM>_v20, ...  for the 7 core markets
#
# The three volatility windows are here so the protocol's robustness clause
# ("the volatility estimation window") is executable rather than aspirational.
# Nothing is computed here beyond closes and trailing volatility — signals,
# positions, benchmarks and tests all happen locally, in versioned code.
#
# >>> Copy EVERYTHING between the BEGIN and END markers and paste it back. <<<
# The printed md5 confirms it arrived intact.
from AlgorithmImports import *
import numpy as np
import pandas as pd
import gzip, base64, hashlib

qb = QuantBook()
START, END = datetime(2009, 1, 1), datetime.now()
TD = 252
SECTORS = {"energy": ["CL", "NG"], "metals": ["GC", "HG"], "grains": ["ZC", "ZS", "ZW"]}
ALL = [s for v in SECTORS.values() for s in v]

# The roll settings validated in the CTA project: OpenInterest mapping (their
# volume/OI roll) and BackwardsRatio normalization, so daily percentage returns
# are true. The protocol's first data requirement is that both roll choices are
# recorded; they are recorded here and echoed into the exported header.
MAP, NORM = DataMappingMode.OpenInterest, DataNormalizationMode.BackwardsRatio
VOL_WINDOWS = [20, 60, 120]


def continuous_closes(sym):
    try:
        fut = qb.add_future(sym, Resolution.DAILY, data_mapping_mode=MAP,
                            data_normalization_mode=NORM, contract_depth_offset=0)
        h = qb.history(fut.symbol, START, END, Resolution.DAILY)
        if h is None or len(h) == 0:
            return None, None
        c = h["close"].copy()
        c.index = pd.DatetimeIndex(c.index.get_level_values(-1)).normalize()
        adjusted = c[~c.index.duplicated(keep="last")].sort_index()

        # Integer-contract sizing needs the mapped contract's actual price.
        # BackwardsRatio levels have an arbitrary historical scale and may not
        # be multiplied by the contract unit. Keep the same mapping rule but
        # request Raw normalization for the execution-price series.
        fut.set_data_normalization_mode(DataNormalizationMode.Raw)
        h_raw = qb.history(fut.symbol, START, END, Resolution.DAILY)
        if h_raw is None or len(h_raw) == 0:
            return adjusted, None
        raw = h_raw["close"].copy()
        raw.index = pd.DatetimeIndex(raw.index.get_level_values(-1)).normalize()
        execution = raw[~raw.index.duplicated(keep="last")].sort_index()
        return adjusted, execution
    except Exception as e:
        print(f"  {sym}: skip ({type(e).__name__})")
        return None, None


served = {s: continuous_closes(s) for s in ALL}
closes = {s: pair[0] for s, pair in served.items()
          if pair[0] is not None and pair[1] is not None and len(pair[0]) > 300}
trade_closes = {s: served[s][1] for s in closes}
panel = pd.DataFrame(closes).sort_index()
trade_panel = pd.DataFrame(trade_closes).sort_index()
print("markets served:", list(panel.columns))
print("daily bars:", {c: int(panel[c].notna().sum()) for c in panel.columns})

daily_ret = panel.pct_change(fill_method=None).clip(-0.5, 0.5)

out = {}
for sym in panel.columns:
    out[f"{sym}_close"] = panel[sym]
    out[f"{sym}_trade_close"] = trade_panel[sym]
    for w in VOL_WINDOWS:
        out[f"{sym}_v{w}"] = daily_ret[sym].rolling(w).std() * np.sqrt(TD)

wide = pd.DataFrame(out)
# Month-end sampling. Every column is a level or a trailing statistic observed AT
# that date, so a row dated t contains only information available at t. The local
# code is responsible for lagging it before it becomes a position.
monthly = wide.resample("ME").last().dropna(how="all")
monthly = monthly[monthly.index >= "2009-06-30"]

body = monthly.round(6).to_csv(float_format="%.6f")
header = (f"# roll: mapping=OpenInterest normalization=BackwardsRatio depth=0\n"
          f"# execution_prices: mapping=OpenInterest normalization=Raw depth=0\n"
          f"# source: QuantConnect native continuous futures\n"
          f"# markets: {','.join(panel.columns)}\n"
          f"# vol_windows_days: {','.join(str(w) for w in VOL_WINDOWS)}\n"
          f"# rows: {len(monthly)}  span: {monthly.index[0].date()} .. {monthly.index[-1].date()}\n")
payload = header + body

print("\nrows:", len(monthly), " cols:", monthly.shape[1],
      " span:", monthly.index[0].date(), "..", monthly.index[-1].date())
print("raw csv bytes:", len(payload))
print("md5:", hashlib.md5(payload.encode()).hexdigest())

blob = base64.b64encode(gzip.compress(payload.encode(), 9)).decode()
print("blob chars:", len(blob))
print("\n=== BEGIN PANEL BLOB ===")
for i in range(0, len(blob), 200):
    print(blob[i:i + 200])
print("=== END PANEL BLOB ===")
