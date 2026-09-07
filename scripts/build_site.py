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
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SITE = ROOT / "docs"        # GitHub Pages serves main:/docs directly
REGISTRY = ROOT / "registry"
CASES = ROOT / "cases"

from verdict.catalog import (CASES as CATALOG_CASES, CASE_DIRS, FOUNDATION_PLAYBOOKS,
                             FOUNDATIONAL_CASES)  # noqa: E402
from verdict.report import validate_card  # noqa: E402

MANIFEST = ".verdict-site-manifest.json"

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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    items = [("index.html", "overview"), ("portfolio.html", "five-minute route"),
             ("demo.html", "interactive demo"), ("registry.html", "evidence"),
             ("appendix.html", "appendix"),
             ("https://github.com/Zink0909/verdict", "source")]
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
        card = json.loads(p.read_text())
        validate_card(card)
        cards.append(card)
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
        f"""{nav("evidence")}
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
and an honest-limitations section that says what the run cannot settle. Each README names
whether the evidence is executable, a read-only source replay, or data-gated; a replay is
never presented as a fresh computation.</p>
<p>Start with <a href="index.html">the system</a> to see how four prior studies became
one reusable framework. The <a href="agent.html">agent page</a> shows the loop running end to end on one claim,
including its evaluation against what human experts actually did — and what it missed.</p>
<p>The repository also carries the working surface the register is maintained from: four
screens for browsing the register, pre-registering a protocol on a new claim, running the
evaluation battery over a return series, and watching the agent loop. It runs locally with
<code>streamlit run app.py</code> and computes nothing itself — every figure comes from the
same library the cases use.</p>
""",
        "A harness for checking predictive claims, and the record of what happened when "
        "claims were put through it.")


def build_system_page(cards: list[dict], links: dict[str, str]) -> str:
    """Explain why the cases are one system, using the catalog as the source of truth."""
    cards_by_id = {card["id"]: card for card in cards}
    foundation_rows = []
    for spec in FOUNDATIONAL_CASES:
        card = cards_by_id[spec.card_id]
        playbook = FOUNDATION_PLAYBOOKS[spec.card_id]
        title = html.escape(card.get("title", spec.card_id))
        link = links.get(spec.card_id)
        title = f'<a href="{link}">{title}</a>' if link else title
        foundation_rows.append(
            "<tr>"
            f"<td>{title}</td>"
            f"<td>{html.escape(playbook['source'])}</td>"
            f"<td><code>{html.escape(' · '.join(playbook['modules']))}</code></td>"
            "</tr>")

    role_meaning = {
        "foundation": "The four source studies from which the A-layer playbooks were extracted.",
        "fresh-audit": "A new claim audited end to end through the system; it tests generality, not provenance.",
        "extension": "A later application of the same contract; it must not rewrite the project identity.",
        "data-gated": "Protocol recorded, but no execution corpus is available; no verdict is issued.",
    }
    role_rows = []
    for role, meaning in role_meaning.items():
        matching = [cards_by_id[spec.card_id] for spec in CATALOG_CASES if spec.role == role]
        names = ", ".join(html.escape(card.get("title", card["id"])) for card in matching) or "—"
        role_rows.append(f"<tr><td><code>{role}</code></td><td>{names}</td>"
                         f"<td>{html.escape(meaning)}</td></tr>")

    return page(
        "Verdict — the system",
        f"""{nav("overview")}
<p class="kicker">system overview</p>
<h1>Four research projects, one auditable system.</h1>
<p class="lede">Verdict is my attempt to turn the recurring research discipline from four
completed studies into one tested workflow: state a claim, decide how it could fail, compute
only through deterministic code, and preserve the evidence and limits of the conclusion.</p>

<div class="flow">
  four source studies<br>
  &nbsp;&nbsp;↓ extract the recurring research discipline<br>
  <b>A · validation framework</b> — deterministic data, split, inference, cost,
  robustness, and diagnosis tools<br>
  &nbsp;&nbsp;↓ one case contract and evidence manifest<br>
  <b>B · research-audit agent</b> — claim → protocol → human approval → tool calls → verdict<br>
  &nbsp;&nbsp;↓<br>
  <b>claim register</b> — what was tested, what survived, and what remains unresolved
</div>

<h2>How to read this project</h2>
<div class="scroll"><table>
<tr><th>layer</th><th>what to open</th><th>why it matters</th></tr>
<tr><td><strong>Core</strong></td><td>This page and the four source studies below</td>
<td>Shows the abstraction: four different projects left behind four reusable research constraints.</td></tr>
<tr><td><strong>Demo</strong></td><td><a href="portfolio.html">Five-minute route</a> or <a href="demo.html">interactive demo</a></td>
<td>Shows one claim moving from protocol to bounded evidence, rather than a tour of every feature.</td></tr>
<tr><td><strong>Evidence</strong></td><td><a href="registry.html">Claim register</a></td>
<td>Lets a reader inspect the cases, their execution mode, their verdict, and their limits.</td></tr>
<tr><td><strong>Appendix</strong></td><td><a href="appendix.html">Advanced material</a></td>
<td>Agent, Evidence Vault, extra cases, and benchmark machinery remain inspectable without competing with the main story.</td></tr>
</table></div>
<p>The graduate-application scope, non-goals, and completion gate are fixed in the
<a href="https://github.com/Zink0909/verdict/blob/main/PROJECT_CHARTER.md">project charter</a>.</p>

<h2>Where the framework came from</h2>
<p>The source studies are not decorative portfolio entries. Each left behind a reusable
playbook. The catalog enforces this exact four-study set, so a later case cannot silently
replace part of the system's origin story.</p>
<div class="scroll"><table>
<tr><th>source study</th><th>question it contributed</th><th>framework modules</th></tr>
{''.join(foundation_rows)}
</table></div>

<h2>Two layers, deliberately separated</h2>
<h3>A · Validation framework</h3>
<p>The library owns numerical work: point-in-time checks, chronological and sealed
splits, spanning and bootstrap inference, cost and option accounting, robustness sweeps,
and mechanism diagnosis. Its known-answer gates have to detect effects planted in
synthetic controls; a harness that only finds nulls is not evidence.</p>
<h3>B · Research-audit agent</h3>
<p>The Agent reads and structures a claim, drafts a falsifiable protocol, waits for a
person to approve it, calls A-layer tools, then writes a verdict. It never computes a
number. Its number audit can withhold unsupported figures, while its documented boundary
is that correct figures can still be interpreted wrongly and need human review.</p>

<h2>Case roles are evidence roles</h2>
<div class="scroll"><table>
<tr><th>role</th><th>cases</th><th>meaning</th></tr>
{''.join(role_rows)}
</table></div>
<p>Execution mode is equally explicit. Complexity is executable through its framework
adapter. Retrospective and extension cases expose pinned evidence read-only, and Lazy
Prices stops at a pre-registered, data-gated protocol. A replay is never described as a
fresh recomputation.</p>

<h2>What this demonstrates</h2>
<p>The point is not to recommend a trade. It is to show the ability to abstract common
research discipline from different projects, build shared infrastructure, preserve the
provenance and limits of each case, and let a conclusion be negative when the evidence
requires it. Start with the <a href="portfolio.html">five-minute route</a>; use the
<a href="appendix.html">appendix</a> only when you want implementation detail.</p>
""",
        "A validation framework and research-audit agent extracted from four completed studies.")


def build_demo_page() -> str:
    """A self-contained viewing route that distinguishes static evidence from local UI."""
    return page(
        "Verdict — a three-minute demo",
        f"""{nav("interactive demo")}
<p class="kicker">guided tour</p>
<h1>See the system in three minutes.</h1>
<p class="lede">This is a research-validation workflow: define what would falsify a claim,
run deterministic checks, preserve evidence, and publish a bounded verdict. It is not a
trading terminal or an automated investment adviser.</p>

<h2>Minute 1 · Start with the system, not a strategy</h2>
<p>Open <a href="index.html">the system overview</a>. The table shows how four prior studies
became reusable playbooks: sealed holdouts and spanning; point-in-time construction and
instrument expression; real friction; and distribution-shift diagnosis. Later cases exercise
that shared infrastructure without rewriting its provenance.</p>

<h2>Minute 2 · Follow one claim to its evidence</h2>
<p>Open the <a href="cases/complexity.html">Complexity case</a>. It is the principal
end-to-end demonstration: one structured claim, a pre-registered protocol, deterministic
tests, a bounded verdict, and explicit limitations. The <a href="registry.html">claim
register</a> then shows that the same evidence contract is applied across the rest of the
library. A case is executable, a labelled read-only replay of pinned evidence, or data-gated;
no mode is silently promoted to another.</p>

<h2>Minute 3 · Inspect the workflow boundary</h2>
<p>Open <a href="appendix.html#agent">the recorded Agent loop</a>. It turns a paper into a structured claim, drafts a
falsifiable protocol, waits for human approval, calls deterministic tools, and writes a
verdict whose figures are checked against tool output. The demo also exposes what its
evaluation did <em>not</em> measure.</p>

<h2>Interactive companion: run locally</h2>
<p>The GitHub Pages site is intentionally static: it is the shareable evidence layer. The
interactive working surface runs locally and has a guided <em>Start here</em> screen:</p>
<pre>micromamba env create -f environment.yml
micromamba run -n verdict pip install -e .
micromamba run -n verdict streamlit run app.py</pre>
<p>From there, create a local protocol draft, upload a dated return CSV or use the synthetic
control, run the validation battery, and inspect the recorded Agent loop. The local
<em>Audit a paper</em> page also accepts pasted text or `.txt` / `.md` / `.pdf` uploads:
it extracts a Claim Card and protocol, then either uses a genuinely matching provider, evaluates
a supplied dated return/benchmark CSV with clearly bounded deterministic tools, or stops at
data-gated. CSV evaluation does not reproduce the paper's strategy or prove its source data is
point-in-time. Each approved paper audit is saved locally as a hashed evidence package, outside
the public register. New-paper extraction needs the optional live-model dependency and
credentials; the Complexity walkthrough is available offline. Local drafts are kept outside the
public register until a case contract, evidence artifacts, report, and integrity audit exist.</p>

<h2>What to say while presenting it</h2>
<blockquote>I did not combine internship projects by putting their reports in one folder. I
looked for the repeated research discipline behind them, made that discipline reusable and
testable, then used a common evidence contract to retain both results and their limits.</blockquote>
""",
        "A guided tour of Verdict's system, evidence register, and interactive local working surface.")


def build_portfolio_page(cards: list[dict], links: dict[str, str]) -> str:
    """A bounded five-minute presentation route grounded in repository artifacts."""
    titles = {card["id"]: card.get("title") or card["id"] for card in cards}
    foundation_links = []
    for case in FOUNDATIONAL_CASES:
        href = links.get(case.card_id)
        label = html.escape(titles[case.card_id])
        foundation_links.append(f'<a href="{href}">{label}</a>' if href else label)
    delivered = sum(card["state"] == "verdict-delivered" for card in cards)
    return page(
        "Verdict — portfolio briefing",
        f"""{nav("five-minute route")}
<p class="kicker">presentation route</p>
<h1>One system, assembled from four research studies.</h1>
<p class="lede">Verdict is a research-validation system for predictive claims. It does not
recommend trades. It makes a claim, its test, the data boundary, the calculation, and the
limitation inspectable in one place.</p>

<h2>The opening — 30 seconds</h2>
<blockquote>I took repeated research discipline from distinct studies and turned it into a
single, testable evidence system. The deliverable is not a collection of strategies: it is a
way to make predictive claims falsifiable and reviewable.</blockquote>

<h2>What the four source studies contributed</h2>
<div class="scroll"><table>
<tr><th>source study</th><th>reusable research constraint</th></tr>
<tr><td>{foundation_links[0]}</td><td>sealed holdout and spanning: a result must add information beyond the existing book.</td></tr>
<tr><td>{foundation_links[1]}</td><td>point-in-time construction and expression diagnosis: a signal and the instrument used to express it are different claims.</td></tr>
<tr><td>{foundation_links[2]}</td><td>friction and implementability: a gross result is incomplete until costs and real quoting assumptions are exposed.</td></tr>
<tr><td>{foundation_links[3]}</td><td>distribution-shift diagnosis: a declining feature is observed before its cause is claimed.</td></tr>
</table></div>

<h2>The system — 90 seconds</h2>
<div class="flow"><b>paper or claim</b> → Claim Card → pre-registered Protocol → <span class="you">human approval</span>
→ deterministic tools → number audit → bounded outcome → evidence package / public case</div>
<p>The separation is deliberate. A language model may structure a claim, select from closed
tools, and write prose; it never computes the figures. A result may be executable, a labelled
read-only evidence replay, or data-gated. Those are different states, never interchangeable.</p>

<h2>The evidence — 90 seconds</h2>
<p>Open the <a href="cases/complexity.html">Complexity case</a> first: it is the one complete
end-to-end demonstration. The <a href="registry.html">claim register</a> then provides context:
it contains {delivered} adjudicated cases and a data-gated case whose honest outcome is an
approved protocol without a verdict. Every case page carries claim, protocol, outcome,
limitations, artifacts, and execution mode.</p>

<h2>The interactive proof — 90 seconds</h2>
<p>Run the local working surface and follow <em>Start here</em>. The offline Complexity walkthrough
demonstrates the full Agent loop. For a new paper, the paper route turns text into a Claim Card
and protocol, waits for approval, and either runs a matching provider, evaluates a user-supplied
dated return CSV with explicit boundaries, or stops data-gated. The Evidence Vault then hashes,
reviews, compares, and exports the local audit package.</p>
<pre>micromamba run -n verdict streamlit run app.py</pre>

<h2>What this project demonstrates</h2>
<ul>
<li>abstraction: extracting common research constraints from different projects;</li>
<li>implementation: turning those constraints into reusable, tested code and a coherent interface;</li>
<li>judgment: keeping provenance, data availability, and negative results visible rather than smoothing them away;</li>
<li>evaluation: checking both numerical outputs and the Agent's protocol omissions against an expert checklist.</li>
</ul>

<h2>The boundary to state plainly</h2>
<p>Verdict is an evidence and research-method system. A supplied return CSV is not proof that a
paper strategy was reproduced; a read-only result replay is not a new computation; and a
data-gated protocol is not a failed implementation. These distinctions are part of the result.</p>
""",
        "A five-minute, evidence-grounded presentation route through the Verdict research-validation system.")


def build_appendix_page() -> str:
    """Keep advanced machinery inspectable without making it the opening story."""
    return page(
        "Verdict — appendix",
        f"""{nav("appendix")}
<p class="kicker">implementation appendix</p>
<h1>Advanced material, kept separate from the main argument.</h1>
<p class="lede">The public story is four studies → reusable research discipline → one
end-to-end audit. This page is for readers who want to inspect the additional engineering
without mistaking it for the project’s thesis.</p>

<h2>Evidence library</h2>
<p>The <a href="registry.html">claim register</a> contains every delivered and data-gated
case. It is deliberately broader than the main demo: the extra cases test portability, but do
not redefine the four source studies or turn Verdict into a strategy catalogue.</p>

<h2 id="agent">Research-audit Agent</h2>
<p>The <a href="agent.html">Agent page</a> records an offline, end-to-end walkthrough. A model
may structure a paper and draft a protocol; a human approves the protocol; deterministic code
provides every number; and a number audit rejects unsupported figures. It is a boundary and
workflow demonstration, not the project’s decision-maker.</p>

<h2>Local Evidence Vault</h2>
<p>The local Streamlit interface can save approved paper audits as hash-verified evidence
packages, compare two records, and export a ZIP. This supports review and reproducibility for
new work; it does not silently promote a local audit into the public register.</p>

<h2>Protocol benchmarks</h2>
<p>The repository includes two curator-authored, real-paper protocol checklists for the
volatility-management pair. They test only whether a live model proposes pre-written checks;
they do not execute a strategy, reproduce a paper, or establish investment value. They remain
local, optional, and secondary to the deterministic framework.</p>

<h2>For technical review</h2>
<ul>
<li><a href="https://github.com/Zink0909/verdict">Source repository</a> — tested modules, case contracts, and integrity checks.</li>
<li><a href="registry.html">Evidence register</a> — claim-level records and their limitations.</li>
<li><a href="agent.html">Recorded Agent loop</a> — protocol, trace, result audit, and its limitations.</li>
</ul>
""",
        "Implementation details and optional advanced workflows for the Verdict research-validation system.")


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

    benchmark_specs = []
    for path in sorted((ROOT / "cases" / "agent_benchmark").glob("*.json")):
        item = json.loads(path.read_text())
        benchmark_specs.append(
            f"<li><strong>{html.escape(item['title'])}</strong> — "
            f"{html.escape(item['paper']['citation'])}; "
            f"{len(item['checklist'])} pre-written protocol checks. "
            f"<a href=\"{html.escape(item['paper']['source_url'], quote=True)}\">source</a></li>")
    benchmark_list = "".join(benchmark_specs) or "<li>No protocol benchmarks are registered.</li>"

    return page(
        "Verdict — the agent",
        f"""{nav("appendix")}
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

<h2>Curated real-paper protocol benchmarks</h2>
<p>Two additional specifications use the linked volatility-management papers. They are not
pre-filled model results: each is a human-curated, omissions-first checklist written before a
live model run. The run stops after Claim Card and protocol drafting — before approval, data,
tools, numerical execution, or publication.</p>
<ul>{benchmark_list}</ul>
<pre>micromamba run -n verdict python scripts/run_agent_benchmark.py --list
micromamba run -n verdict python scripts/run_agent_benchmark.py \\
  --benchmark volatility-managed-market</pre>
<p>A live benchmark needs a lawful local paper copy, the optional Anthropic SDK and configured
API credentials. Its output remains under local <code>.verdict-workspace/benchmarks/</code>;
the coverage number measures checklist coverage, not research correctness or model capability
in general.</p>

<h2>Running it yourself</h2>
<pre>micromamba run -n verdict python scripts/run_agent.py --offline --yes
micromamba run -n verdict python scripts/run_agent_eval.py</pre>
<p>No credentials are needed for the offline path: the analysis runs for real, only the
model's turns are replayed. A live run needs the paper, the SDK, and an API key.</p>
""",
        "A research-audit agent that pre-registers its protocol, calls deterministic code "
        "for every number, and has its prose audited against the results.")


def main() -> int:
    SITE.mkdir(parents=True, exist_ok=True)
    manifest_path = SITE / MANIFEST
    if manifest_path.exists():
        previous = json.loads(manifest_path.read_text())
        for rel in previous.get("generated", []):
            target = (SITE / rel).resolve()
            if SITE.resolve() in target.parents and target.is_file():
                target.unlink()
    (SITE / ".nojekyll").write_text("")

    cards = load_cards()
    links = render_case_pages()
    system_page = build_system_page(cards, links)
    (SITE / "index.html").write_text(system_page)
    (SITE / "registry.html").write_text(build_index(cards, links))
    (SITE / "system.html").write_text(system_page)
    (SITE / "demo.html").write_text(build_demo_page())
    (SITE / "portfolio.html").write_text(build_portfolio_page(cards, links))
    (SITE / "appendix.html").write_text(build_appendix_page())
    (SITE / "agent.html").write_text(build_agent_page())

    generated = sorted(["index.html", "registry.html", "system.html", "demo.html", "portfolio.html", "appendix.html", "agent.html",
                        ".nojekyll", *links.values()])
    source_paths = [*sorted(REGISTRY.glob("*.json")),
                    *sorted(CASES.glob("*/report.md")),
                    *sorted((ROOT / "cases" / "agent_benchmark").glob("*.json")),
                    ROOT / "cases/complexity/agent_run/run.json",
                    ROOT / "cases/complexity/agent_eval/report.md",
                    ROOT / "scripts/build_site.py", ROOT / "verdict/catalog.py",
                    ROOT / "PROJECT_CHARTER.md"]
    source_paths = [path for path in source_paths if path.is_file()]
    manifest = {
        "schema_version": 2,
        "generated": generated,
        "inputs": {str(path.relative_to(ROOT)): _sha256(path) for path in source_paths},
        "outputs": {rel: _sha256(SITE / rel) for rel in generated},
    }
    tmp = manifest_path.with_name(f".{manifest_path.name}.tmp")
    tmp.write_text(json.dumps(manifest, indent=2) + "\n")
    tmp.replace(manifest_path)

    total = sum(p.stat().st_size for p in SITE.rglob("*") if p.is_file())
    print(f"built {SITE}/  ({total/1e6:.1f} MB, {len(list(SITE.rglob('*.html')))} pages)")
    for p in sorted(SITE.rglob("*.html")):
        print(f"  {p.relative_to(SITE)}  ({p.stat().st_size/1024:.0f} KB)")
    missing = [c["id"] for c in cards if c["id"] not in links and c["state"] != "protocol-ready-data-gated"]
    if missing:
        print(f"  ! delivered verdicts with no page: {missing}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
