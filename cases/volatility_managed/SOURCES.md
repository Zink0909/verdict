# Sources — bounded volatility-managed market audit

## Paper

- Alan Moreira and Tyler Muir (2017), *Volatility-Managed Portfolios*,
  *Journal of Finance* 72(4), 1611–1644, DOI
  [`10.1111/jofi.12513`](https://doi.org/10.1111/jofi.12513).
- Working-paper reading copy: NBER Working Paper 22208,
  [`w22208.pdf`](https://www.nber.org/system/files/working_papers/w22208/w22208.pdf).
  It is deliberately **not** committed: the case records the public source rather
  than redistributing the paper PDF. Local download SHA-256 on 2026-09-07:
  `be1ea92102e1394e9ddec9545489902f45e5a07b42bd4c42faf8ee372e99fa7a`.

## Public input data

- Kenneth R. French Data Library, **Fama/French 5 Factors (2x3) [Daily]**,
  downloaded 2026-09-07 from
  [`F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip).
- Pinned archive SHA-256:
  `478350b8d60831351fbf754bc593fc0112b013552c24639c10902e1f26d7f306`.
  The downloaded file states it was created from the July 2026 CRSP data cut.

## What this source set can and cannot support

It supports a reconstruction of the paper's **market** volatility-management
transformation on public daily market excess returns. It does not contain the
paper's full nine-factor/currency data, its historical data vintage, or its
precise published sample. This is therefore a bounded fresh audit, not a
byte-for-byte reproduction of every result in Moreira and Muir.
