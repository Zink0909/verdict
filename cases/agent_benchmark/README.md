# Agent protocol benchmark

This directory evaluates **only** the Agent's first two actions: extracting a
Claim Card from a paper and drafting a protocol before it sees any data. It is
not a strategy backtest, a paper reproduction, or an investment recommender.

The two gold specifications are deliberately paired:

- `volatility-managed-market.json` asks whether a protocol can formulate a
  bounded public-data test of Moreira and Muir's volatility-management claim.
- `volatility-managed-realtime.json` asks whether it can formulate the
  real-time portfolio-choice challenge articulated by Cederburg et al.

Each file is an auditable human checklist, written before a model run and
limited to public source metadata and research-method requirements. It neither
contains paper text nor represents the papers' authors as endorsing the
checklist. The actual PDFs are optional, ignored local reading copies specified
by each file's `paper.local_default` field.

Run one benchmark only after configuring an Anthropic API key:

```bash
micromamba run -n verdict python scripts/run_agent_benchmark.py --list
micromamba run -n verdict python scripts/run_agent_benchmark.py \
  --benchmark volatility-managed-market
```

The command extracts the claim and drafts a protocol. It does not approve or
execute the protocol, call a data provider, or publish anything. Its model
output is stored in the ignored local `.verdict-workspace/benchmarks/` folder,
along with the exact checklist, SHA-256 of the supplied paper text, run JSON,
and an omissions-first report. Use `--paper PATH` to provide another lawful
local copy of the same paper.
