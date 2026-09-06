# Sources — bounded real-time volatility-management audit

- Scott Cederburg, Michael O'Doherty, Feifei Wang and Xuemin Yan (2020),
  *On the Performance of Volatility-Managed Portfolios*, *Journal of Financial
  Economics* 138, 95–117, DOI
  [`10.1016/j.jfineco.2020.03.013`](https://doi.org/10.1016/j.jfineco.2020.03.013).
  Local reading-copy SHA-256 on 2026-09-07:
  `5f82689700a360bed1fd371637d4a62090c6715d0cc9bd85c36fc78bc6129919`.
  The PDF is not committed.
- The public daily Fama/French five-factor archive is reused exactly from
  [`../volatility_managed/SOURCES.md`](../volatility_managed/SOURCES.md), including
  its SHA-256 and current-CRSP-vintage boundary.

The paper evaluates real-time allocation between managed and original portfolios
using past data, risk-free cash, risk aversion 5, and a leverage constraint 5.
This case implements a transparent market-only expanding-window analogue. It is
not a reproduction of the paper's 103-strategy study or its full portfolio
construction choices.
