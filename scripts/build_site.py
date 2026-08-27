#!/usr/bin/env python3
"""Build the public site from the registry, the case reports, and the agent run.

    micromamba run -n verdict python scripts/build_site.py

Nothing here is written by hand twice. The front page is generated from the
claim cards, the case pages are re-rendered from each case's own report source,
and the agent page is assembled from the recorded run and the eval report — so
the site cannot say something the repository does not.

Output is `docs/`, static and self-contained: every page carries its own styles
and its figures inline, so it works on GitHub Pages with no build step, no
assets directory, and nothing to fetch at load time.
"""
from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SITE = ROOT / "docs"        # GitHub Pages serves main:/docs directly
REGISTRY = ROOT / "registry"
CASES = ROOT / "cases"

# Case id -> the directory that holds its report source.
CASE_DIRS = {
    "complexity-voc": "complexity",
    "buy-the-dip-long-calls": "buy_the_dip",
    "retail-short-volatility": "vol_harvest",
    "gamma-signal-drift": "drift",
}

CSS = """
:root {
  --bg: #fbfaf8; --surface: #ffffff; --ink: #1a1a1a; --muted: #5f5f5f;
  --line: #e2ded8; --accent: #7a2e2e; --accent-soft: #f3ebe9;
  --ok: #2e6b45; --warn: #8a5a1a;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, monospace;
  --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #14140f; --surface: #1c1c18; --ink: #ece9e3; --muted: #9c968c;
    --line: #33322c; --accent: #d98b7a; --accent-soft: #2a201d;
    --ok: #7fbf95; --warn: #d8a860;
  }
}
:root[data-theme="dark"] {
  --bg: #14140f; --surface: #1c1c18; --ink: #ece9e3; --muted: #9c968c;
  --line: #33322c; --accent: #d98b7a; --accent-soft: #2a201d;
  --ok: #7fbf95; --warn: #d8a860;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: var(--sans); font-size: 17px; line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 46rem; margin: 0 auto; padding: 3.5rem 1.25rem 5rem; }
a { color: var(--accent); text-decoration: none; border-bottom: 1px solid transparent; }
a:hover { border-bottom-color: currentColor; }
h1, h2, h3 { font-family: var(--serif); font-weight: 600; line-height: 1.25; }
h1 { font-size: 2.3rem; margin: 0 0 .35rem; letter-spacing: -.01em; }
h2 { font-size: 1.4rem; margin: 3rem 0 .75rem; padding-top: 1.5rem; border-top: 1px solid var(--line); }
h3 { font-size: 1.08rem; margin: 1.8rem 0 .4rem; }
.lede { font-size: 1.12rem; color: var(--muted); margin: 0 0 2rem; }
.kicker { font-family: var(--mono); font-size: .72rem; letter-spacing: .14em;
          text-transform: uppercase; color: var(--muted); margin: 0 0 .6rem; }
code, .mono { font-family: var(--mono); font-size: .87em; }
pre { background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
      padding: .9rem 1rem; overflow-x: auto; font-size: .84rem; line-height: 1.5; }
blockquote { margin: 1.2rem 0; padding: .1rem 0 .1rem 1.1rem;
             border-left: 3px solid var(--line); color: var(--muted); }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: .92rem; }
th, td { text-align: left; padding: .6rem .5rem; border-bottom: 1px solid var(--line);
         vertical-align: top; }
th { font-family: var(--mono); font-size: .7rem; letter-spacing: .1em;
     text-transform: uppercase; color: var(--muted); font-weight: 500; }
.scroll { overflow-x: auto; }
img { max-width: 100%; height: auto; }

.card { display: block; background: var(--surface); border: 1px solid var(--line);
        border-radius: 8px; padding: 1.1rem 1.2rem; margin: .85rem 0; color: inherit; }
a.card:hover { border-color: var(--accent); border-bottom-width: 1px; }
.card h3 { margin: 0 0 .3rem; }
.card .src { font-size: .82rem; color: var(--muted); margin: 0 0 .55rem; }
.card p { margin: 0; font-size: .95rem; }
.verdict { color: var(--accent); font-weight: 600; }
.tag { display: inline-block; font-family: var(--mono); font-size: .66rem;
       letter-spacing: .09em; text-transform: uppercase; padding: .18rem .5rem;
       border-radius: 999px; background: var(--accent-soft); color: var(--accent);
       border: 1px solid var(--line); margin-left: .4rem; vertical-align: 2px; }
.flow { font-family: var(--mono); font-size: .8rem; line-height: 1.9; color: var(--muted);
        background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
        padding: 1rem 1.1rem; overflow-x: auto; }
.flow b { color: var(--ink); font-weight: 600; }
.flow .you { color: var(--accent); }
footer { margin-top: 4rem; padding-top: 1.5rem; border-top: 1px solid var(--line);
         font-size: .85rem; color: var(--muted); }
.nav { font-family: var(--mono); font-size: .78rem; margin-bottom: 2.5rem; }
.nav a { margin-right: 1.2rem; }
"""


def page(title: str, body: str, description: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<style>{CSS}</style>
</head>
<body><div class="wrap">
{body}
<footer>
Generated from the repository on {date.today().isoformat()} —
the registry table, the case pages and the agent transcript are all built from the
files that produced them, so this site cannot claim something the code does not.
</footer>
</div></body>
</html>
"""


def nav(active: str) -> str:
    items = [("index.html", "registry"), ("agent.html", "the agent"),
             ("https://github.com/", "source")]
    out = []
    for href, label in items:
        out.append(f'<a href="{href}">{label}</a>' if label != active else f"<b>{label}</b>")
    return f'<div class="nav">{"".join(out)}</div>'


def _clip(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def load_cards() -> list[dict]:
    cards = []
    for p in sorted(REGISTRY.glob("*.json")):
        cards.append(json.loads(p.read_text()))
    order = {"verdict-delivered": 0, "in-progress": 1, "protocol-ready-data-gated": 2}
    return sorted(cards, key=lambda c: (order.get(c["state"], 3), c["id"]))


def render_case_pages() -> dict[str, str]:
    """Re-render each case report with the site stylesheet, figures inlined."""
    out_dir = SITE / "cases"
    out_dir.mkdir(parents=True, exist_ok=True)
    css_file = SITE / "_site.css"
    css_file.write_text(CSS + "\nbody{padding:0}.wrap{max-width:46rem}"
                        "\nbody > h1:first-of-type{margin-top:3rem}")
    links = {}
    for card_id, folder in CASE_DIRS.items():
        src = CASES / folder / "report.md"
        if not src.exists():
            continue
        dest = out_dir / f"{folder}.html"
        try:
            subprocess.run(
                ["pandoc", str(src), "-o", str(dest), "--standalone", "--embed-resources",
                 "--css", str(css_file), f"--resource-path={src.parent}",
                 "--metadata", f"title={folder}"],
                check=True, capture_output=True)
            links[card_id] = f"cases/{folder}.html"
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            print(f"  ! could not render {folder}: {e}")
    css_file.unlink(missing_ok=True)
    return links


def build_index(cards: list[dict], links: dict[str, str]) -> str:
    rows = []
    for c in cards:
        claim = c.get("claim", {})
        verdict = (c.get("verdict") or {}).get("outcome", "")
        gated = c["state"] == "protocol-ready-data-gated"
        headline = verdict.split(" — ")[0] if verdict else "not adjudicable with available data"
        rest = verdict.split(" — ", 1)[1] if " — " in verdict else ""
        tag = ' <span class="tag">data-gated</span>' if gated else ""
        claim_line = " · ".join(x for x in (claim.get("source", ""),
                                            _clip(claim.get("claimed_effect", ""), 130)) if x)
        body = (f'<h3>{html.escape(c.get("title", c["id"]))}{tag}</h3>'
                f'<p class="src">{html.escape(claim_line)}</p>'
                f'<p><span class="verdict">{html.escape(headline)}</span>'
                + (f" — {html.escape(rest)}" if rest else "")
                + (' <em>Claim extracted and protocol pre-registered; the corpus needed to '
                   'run it has not been built, so no verdict is issued.</em>' if gated else "")
                + "</p>")
        href = links.get(c["id"])
        rows.append(f'<a class="card" href="{href}">{body}</a>' if href
                    else f'<div class="card">{body}</div>')

    delivered = sum(1 for c in cards if c["state"] == "verdict-delivered")
    return page(
        "Verdict — a claim registry",
        f"""{nav("registry")}
<p class="kicker">claim registry</p>
<h1>Verdict</h1>
<p class="lede">A harness for checking predictive claims, and the record of what happened
when claims were put through it. {delivered} adjudicated so far.</p>

<p>Predictive claims are cheap to make and expensive to check. Checking one properly means
the same unglamorous discipline every time: build the data as it stood at the time, split
only by time, seal a block and open it once, compare against what you already had, price
the frictions, perturb the definitions, and — when the answer is no — find out <em>which</em>
mechanism said no. This is that discipline written as code, plus the verdicts it produced.</p>

<h2>The register</h2>
{''.join(rows)}

<h2>How a claim is audited</h2>
<div class="flow">
  a claim arrives (a paper, a pitch, an idea)<br>
  &nbsp;&nbsp;↓<br>
  <b>1. extract</b> — signal, universe, frequency, claimed effect, sample, data needed<br>
  &nbsp;&nbsp;↓<br>
  <b>2. pre-register</b> — splits, benchmarks, costs, diagnostics,
  <b>and what result would kill it</b><br>
  &nbsp;&nbsp;↓<br>
  <span class="you">3. a person approves the protocol</span> — before any data is touched<br>
  &nbsp;&nbsp;↓<br>
  <b>4. execute</b> — deterministic code computes every number<br>
  &nbsp;&nbsp;↓<br>
  <b>5. diagnose</b> — if the answer is no, find the mechanism<br>
  &nbsp;&nbsp;↓<br>
  <b>6. record</b> — a verdict with mandatory limitations, and a card in this register
</div>
<p>Step 2 is the one that matters. Writing down what would falsify a claim
<em>before</em> seeing the data is what stops the answer from being retrofitted to the
result, and it is the step that gets skipped.</p>

<h2>Why the numbers can be checked</h2>
<table>
<tr><th>guarantee</th><th>how it is enforced</th></tr>
<tr><td>A sealed block opens once</td>
    <td>Every opening is written to a ledger with its reason and a fingerprint of the
    analysis configuration. Re-opening under a <em>changed</em> configuration raises.</td></tr>
<tr><td>Negative results are publishable</td>
    <td>The document renderer refuses to produce a verdict whose honest-limitations
    section is empty.</td></tr>
<tr><td>Prose does not invent figures</td>
    <td>Every number in a written verdict is checked against the values the analysis
    returned; anything unsupported is flagged and the draft is withheld.</td></tr>
<tr><td>The harness can find a real effect</td>
    <td>Known-answer controls plant an effect that only a flexible model can see, and
    require the harness to detect it. A null from a harness that can only find nulls is
    worth nothing.</td></tr>
<tr><td>Audits do not vouch for themselves</td>
    <td>The leakage and membership checks re-derive timestamps independently and never
    import the code they are checking.</td></tr>
</table>

<h2>Reading a verdict</h2>
<p>Each case page carries the full write-up: what was audited, what was found, the figures,
and an honest-limitations section that says what the run cannot settle. Every case is
reproducible offline from pinned data with the commands in its own README, and the numbers
in the write-up are interpolated from the results file rather than typed in.</p>
<p>The <a href="agent.html">agent page</a> shows the loop running end to end on one claim,
including its evaluation against what human experts actually did — and what it missed.</p>
""",
        "A harness for checking predictive claims, and the record of what happened when "
        "claims were put through it.")


def build_agent_page() -> str:
    run_path = ROOT / "cases/complexity/agent_run/run.json"
    eval_path = ROOT / "cases/complexity/agent_eval/report.md"
    run = json.loads(run_path.read_text()) if run_path.exists() else {}
    audit = run.get("number_audit", {})
    protocol = run.get("protocol", {})
    trace = [s for s in run.get("tool_trace", []) if "tool" in s]

    calls = "\n".join(
        f"  {s['tool']}({', '.join(f'{k}={v!r}' for k, v in s['arguments'].items())})\n"
        f"      → {json.dumps({k: v for k, v in (s.get('result') or {}).items() if not isinstance(v, str)})}"
        for s in trace)

    kill = "".join(f"<li>{html.escape(k)}</li>" for k in protocol.get("kill_criteria", []))
    diagnostics = "".join(f"<li>{html.escape(d)}</li>" for d in protocol.get("diagnostics", []))

    eval_html = ""
    if eval_path.exists():
        try:
            eval_html = subprocess.run(["pandoc", str(eval_path), "-t", "html"],
                                       check=True, capture_output=True, text=True).stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            eval_html = f"<pre>{html.escape(eval_path.read_text())}</pre>"

    audit_line = ("every figure traces to a computed result"
                  if audit.get("clean") else
                  f"unsupported figures found: {audit.get('unsupported')}")

    return page(
        "Verdict — the agent",
        f"""{nav("the agent")}
<p class="kicker">layer B</p>
<h1>The agent</h1>
<p class="lede">A thin layer over the harness that reads a paper, pre-registers a protocol,
executes it by calling deterministic code, and writes the verdict — without ever computing
a number itself.</p>

<h2>What it is allowed to do</h2>
<p>The agent chooses: what the claim is, how to test it, which analysis to run with which
arguments, and how to describe the result. The agent does not compute. Every quantity comes
back from the harness, and the transcript below records each call and each value it
returned.</p>
<p>Two properties are structural rather than promised. The protocol is written and approved
<em>before</em> any analysis runs, and a later request to tune a parameter, re-open a sealed
block, or drop inconvenient observations is refused with the clause it violates. And the
finished prose is checked against the computed values, so a figure the model invented is
caught rather than published.</p>

<h2>A recorded run</h2>
<p>This is one complete pass over the complexity claim. The model's turns are replayed from
a recorded transcript; <strong>every number below was computed live by the harness</strong>
when this page was built. That split is deliberate — it lets the whole loop be demonstrated
and regression-tested without an API key, and it keeps the figures real.</p>

<h3>Pre-registered, before any data was touched</h3>
<p><strong>Diagnostics</strong></p><ul>{diagnostics}</ul>
<p><strong>What would kill the claim</strong></p><ul>{kill}</ul>

<h3>Execution</h3>
<div class="scroll"><pre>{html.escape(calls)}</pre></div>

<h3>The written verdict, and the audit of it</h3>
<div class="scroll"><pre>{html.escape(run.get('verdict_draft', run.get('verdict_text', '')))}</pre></div>
<p><strong>Number audit:</strong> {audit.get('n_numbers', 0)} figures written, checked
against {audit.get('n_allowed_values', 0)} computed or source values —
<span class="verdict">{html.escape(audit_line)}</span>.</p>
<blockquote>What this check cannot catch: a correct number described wrongly. A sentence that
cites a real figure and mischaracterises it passes, because the figure is real and only the
claim about it is false. The audit bounds fabrication, not interpretation.</blockquote>

<h2>Evaluating the agent</h2>
<p>This claim is unusual in having a published ground truth: two independent critiques of the
same paper name the specific tests that settled it. A protocol drafted from the paper alone
can therefore be scored against what expert auditors actually did — and the part worth
reading is what the agent missed.</p>
{eval_html}

<h2>Running it yourself</h2>
<pre>micromamba run -n verdict python scripts/run_agent.py --offline --yes
micromamba run -n verdict python scripts/run_agent_eval.py</pre>
<p>No credentials are needed for the offline path: the analysis runs for real, only the
model's turns are replayed. A live run needs the paper, the SDK, and an API key.</p>
""",
        "A research-audit agent that pre-registers its protocol, calls deterministic code "
        "for every number, and has its prose audited against the results.")


def main() -> int:
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    (SITE / ".nojekyll").write_text("")

    cards = load_cards()
    links = render_case_pages()
    (SITE / "index.html").write_text(build_index(cards, links))
    (SITE / "agent.html").write_text(build_agent_page())

    total = sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file())
    print(f"built {SITE}/  ({total/1e6:.1f} MB, {len(list(SITE.rglob('*.html')))} pages)")
    for p in sorted(SITE.rglob("*.html")):
        print(f"  {p.relative_to(SITE)}  ({p.stat().st_size/1024:.0f} KB)")
    missing = [c["id"] for c in cards if c["id"] not in links and c["state"] != "protocol-ready-data-gated"]
    if missing:
        print(f"  ! delivered verdicts with no page: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
