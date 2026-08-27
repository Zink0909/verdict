# Pinned data — volatility-harvesting case

| file | what it is |
|---|---|
| `grid_phase1.csv` | the source study's 72-configuration modelled grid (strike delta x take-profit x stop x entry filter x holding period), friction 0.05 index points per leg |
| `grid_phase2.csv` | the source study's 36-configuration grid (entry gate x strike delta x spread width), same friction |
| `realchain_results.json` | the three configurations run against real option chains, the friction sensitivity table, and the premise measurement — recorded from the source project's authority documents, with provenance inside the file |

Both CSVs are byte-for-byte the source study's outputs except that **column headers and
gate labels were translated from Chinese to English at pin time**; no value was altered.
The mapping applied was:

```
n_trades <- 笔数            total_return_pct <- 总收益%      cagr_pct <- CAGR%
maxdd_pct <- maxDD%         win_pct <- 胜率%                expectancy_usd <- 期望$/笔
worst_trade_usd <- 最大单亏$ gate <- 闸门                    width_pct <- 宽度%
n_trades_post2021 <- 2021后笔数                             last_entry <- 最后入场

gate values:  none <- v1无闸门   contango>=1.00 <- contango≥1.00   contango>=1.05 <- contango≥1.05
```

The grids reproduce the source study's authoritative report exactly — its stated winner
(45-delta / 1.5% wide) appears here with 274 trades, 81 after 2021, +$17.1 per trade,
CAGR +0.7%, Sharpe 0.25, matching the report line for line.
