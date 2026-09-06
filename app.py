"""Verdict — the working surface.

    micromamba run -n verdict streamlit run app.py

The library underneath is the system; this is the way in. Four things you can do
without writing a line of code:

  Start here  take the three-minute guided tour of the system
  Register    browse every claim that has been adjudicated, and what it cost
  New claim   draft a claim card and pre-register a protocol locally — the step
              that decides whether a claim is worth weeks of work, done in an hour
  Evaluate    point at a return series and get the whole battery: interval,
              spanning, cost sensitivity, breakeven, the diagnosis playbooks,
              and a verdict document that will not render without limitations
  Agent       watch the loop run end to end

Every number on every screen is computed by the framework's own functions. This
file contains no analysis: it collects inputs, calls the library, and shows what
came back. If it computed anything itself there would be two sources of truth,
and the point of the system is that there is one.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from verdict import costs as C          # noqa: E402
from verdict import diagnose as D       # noqa: E402
from verdict import evaluate as E       # noqa: E402
from verdict import synthetic as S      # noqa: E402
from verdict.catalog import CASE_BY_ID, CASE_DIRS    # noqa: E402
from verdict.report import VerdictReport, validate_card, write_card  # noqa: E402
from verdict.schema_help import CLAIM_FIELDS, PROTOCOL_FIELDS      # noqa: E402
from verdict.splits import HoldoutAlreadyUnsealed, SealedHoldout   # noqa: E402

st.set_page_config(page_title="Verdict", page_icon="⚖", layout="centered")

REGISTRY = ROOT / "registry"
DRAFT_REGISTRY = ROOT / ".verdict-workspace" / "claims"
STATE_LABEL = {"verdict-delivered": "verdict delivered",
               "protocol-ready-data-gated": "protocol ready · data-gated",
               "in-progress": "in progress"}


# --------------------------------------------------------------- helpers ----

def lines(text: str) -> list[str]:
    return [x.strip() for x in (text or "").splitlines() if x.strip()]


def load_cards() -> list[dict]:
    order = {"verdict-delivered": 0, "in-progress": 1, "protocol-ready-data-gated": 2}
    cards = []
    for p in sorted(REGISTRY.glob("*.json")):
        card = json.loads(p.read_text())
        validate_card(card)
        cards.append(card)
    return sorted(cards, key=lambda c: (order.get(c["state"], 3), c["id"]))


def example_series(seed: int = 0) -> pd.DataFrame:
    """A synthetic series, clearly labelled, so the screen can be tried immediately."""
    X, r = S.planted_linear(180, seed=seed)
    idx = pd.date_range("2011-01-31", periods=180, freq="ME")
    return pd.DataFrame({"date": idx, "return": r,
                         "benchmark": 0.35 * r + np.random.default_rng(seed).normal(0, .03, 180)})


# ---------------------------------------------------------------- pages ----

def page_register() -> None:
    st.title("The register")
    st.caption("Every claim that has been put through the harness, and what came of it.")
    cards = load_cards()
    delivered = sum(1 for c in cards if c["state"] == "verdict-delivered")
    st.markdown(f"**{len(cards)} claims on the register — {delivered} adjudicated.**")

    for c in cards:
        claim, verdict = c.get("claim", {}), c.get("verdict") or {}
        gated = c["state"] == "protocol-ready-data-gated"
        with st.container(border=True):
            st.markdown(f"### {c.get('title', c['id'])}")
            st.caption(f"{claim.get('source','')} · {STATE_LABEL.get(c['state'], c['state'])}")
            if gated:
                why = c.get("why_not_adjudicated", {})
                st.info(f"**Not adjudicable here.** {why.get('blocker','')}. "
                        f"{why.get('detail','')}")
            else:
                st.markdown(f"**{verdict.get('outcome','')}**")
            with st.expander("the claim, the protocol, the limitations"):
                st.markdown("**Claim**")
                st.json({k: v for k, v in claim.items()}, expanded=False)
                st.markdown("**Protocol**")
                st.json(c.get("protocol", {}), expanded=False)
                if verdict.get("honest_limitations"):
                    st.markdown("**Honest limitations**")
                    for lim in verdict["honest_limitations"]:
                        st.markdown(f"- {lim}")
                folder = CASE_DIRS.get(c["id"])
                rep = ROOT / "cases" / folder / "report.md" if folder else None
                if rep and rep.exists():
                    st.caption(f"full write-up: `{rep.relative_to(ROOT)}` · "
                               f"rendered: `docs/cases/{folder}.html`")


def page_start_here() -> None:
    """A short, honest route through the interactive surface for a live demo."""
    st.title("Start here")
    st.caption("A three-minute tour of the research-validation system — not a trading demo.")
    st.info("Verdict asks a narrow question: what evidence would make a predictive claim fail, "
            "and can the result be checked afterwards? The interface is a working surface for "
            "that question; it does not recommend trades or connect to a broker.")

    st.subheader("0 · Give the system a paper")
    st.write("Paste paper text or upload a `.txt`, `.md`, or `.pdf` paper. The system extracts "
             "a claim and drafts a protocol before it is allowed to access any provider.")
    if st.button("Open Audit a paper", type="primary"):
        st.session_state["section"] = "Audit a paper"
        st.rerun()

    st.subheader("1 · Start with a claim, before touching data")
    st.write("Draft a claim card and a protocol with explicit kill criteria. It saves as a "
             "local draft, not as a published verdict.")
    if st.button("Open New claim", type="primary"):
        st.session_state["section"] = "New claim"
        st.rerun()

    st.subheader("2 · Run the deterministic validation battery")
    st.write("Use the built-in synthetic series or upload a dated return CSV. The library, "
             "not this interface, computes time splits, spanning, bootstrap uncertainty, "
             "cost sensitivity, and diagnosis playbooks.")
    if st.button("Open Evaluate a result"):
        st.session_state["section"] = "Evaluate a result"
        st.rerun()

    st.subheader("3 · Inspect the Agent boundary")
    st.write("Watch a recorded end-to-end audit. The Agent chooses a protocol and tool calls; "
             "deterministic code supplies every number, and unsupported figures are withheld.")
    if st.button("Open The agent"):
        st.session_state["section"] = "The agent"
        st.rerun()

    st.caption("For the application-facing narrative, open `docs/index.html` or the GitHub "
               "Pages site first. This local interface is the interactive companion.")


def page_new_claim() -> None:
    st.title("New claim")
    st.caption("Extract the claim, then pre-register how it will be tested — before any "
               "data is touched.")
    st.info("This screen is the cheapest thing the system does. Most of the value is in "
            "the kill criteria: if you cannot write down a result that would falsify the "
            "claim, the claim is not testable and you have just saved yourself the weeks "
            "you were about to spend on it.")
    st.caption("This screen saves a local protocol draft. A claim reaches the public register "
               "only after it has a catalog entry, declared evidence contract, case report, "
               "and integrity checks; a form submission must not weaken those boundaries.")

    with st.form("claim"):
        st.subheader("1 · The claim card")
        claim = {}
        for key, label, help_text, tall in CLAIM_FIELDS:
            claim[key] = (st.text_area(label, help=help_text, key=f"c_{key}", height=80)
                          if tall else st.text_input(label, help=help_text, key=f"c_{key}"))

        st.subheader("2 · The pre-registered protocol")
        proto = {}
        for key, label, help_text, tall in PROTOCOL_FIELDS:
            proto[key] = (st.text_area(label, help=help_text, key=f"p_{key}", height=90)
                          if tall else st.text_input(label, help=help_text, key=f"p_{key}"))

        st.subheader("3 · Can you run it?")
        available = st.radio(
            "Is the data needed to execute this protocol in hand?",
            ["Yes — this goes on the register as in progress",
             "No — register the protocol and record it as data-gated"],
            index=1)
        card_id = st.text_input("Register id", placeholder="short-kebab-case-id")
        title = st.text_input("Short title", placeholder="Plain English, no jargon")
        blocker = st.text_input("If data-gated: what is the blocker?",
                                placeholder="e.g. the corpus has not been built")
        submitted = st.form_submit_button("Validate and save draft", type="primary")

    if not submitted:
        return

    from verdict.schema_help import build_card
    try:
        card = build_card(claim, proto, card_id, title, available.startswith("Yes"), blocker)
    except ValueError as e:
        st.error(f"**Not saved.** {e}")
        return

    target = DRAFT_REGISTRY / f"{card['id']}.json"
    if target.exists():
        st.error(f"**Not saved.** A local draft named `{target.name}` already exists. "
                 "Choose a new id rather than silently overwriting it.")
        return
    path = write_card(card, DRAFT_REGISTRY)
    st.success(f"Saved local draft `{path.name}` — state **{card['state']}**.")
    st.json(card, expanded=False)
    st.caption("This draft is intentionally outside the published register and is ignored by "
               "Git. To publish it, first add a catalog case, evidence artifacts, a report, "
               "and a declared execution mode; then run the repository integrity audit.")


def page_evaluate() -> None:
    st.title("Evaluate a result")
    st.caption("Point at a return series and get the battery. Nothing here is computed by "
               "this page — every figure comes from the library.")

    src = st.radio("Data", ["Upload a CSV", "Use a synthetic example"], horizontal=True)
    if src == "Upload a CSV":
        up = st.file_uploader("A date column, a return column, optional benchmark columns",
                              type=["csv"])
        if up is None:
            st.stop()
        df = pd.read_csv(up)
    else:
        df = example_series()
        st.caption("Synthetic data with a planted signal — for trying the screen, never "
                   "for a conclusion.")

    cols = list(df.columns)
    c1, c2 = st.columns(2)
    date_col = c1.selectbox("Date column", cols, index=0)
    ret_col = c2.selectbox("Return column", cols, index=min(1, len(cols) - 1))
    bench = st.multiselect("Benchmark columns (what the claim must beat)",
                           [c for c in cols if c not in (date_col, ret_col)])
    c3, c4, c5 = st.columns(3)
    ppy = c3.number_input("Periods per year", 1, 365, 12)
    turn = c4.number_input("Turnover per period", 0.0, 10.0, 1.0, 0.1)
    realistic = c5.number_input("Realistic one-way cost (bps)", 0.0, 200.0, 10.0, 1.0)

    selected = [ret_col, *bench]
    clean = df[selected].apply(pd.to_numeric, errors="coerce")
    clean.index = pd.to_datetime(df[date_col], errors="coerce")
    clean = clean.loc[~clean.index.isna()].sort_index()
    if clean.index.has_duplicates:
        st.error("Dates must be unique; aggregate duplicate observations before evaluation.")
        st.stop()
    clean = clean.dropna(subset=[ret_col])
    r = clean[ret_col]
    st.divider()

    st.subheader("Risk-adjusted performance")
    lo, hi = E.block_bootstrap_sharpe_ci(r, periods_per_year=int(ppy))
    m1, m2, m3 = st.columns(3)
    m1.metric("Observations", f"{len(r):,}")
    m2.metric("Mean per period", f"{r.mean():+.4f}")
    m3.metric("Sharpe (annualized)", f"{E.sharpe(r, int(ppy)):.2f}",
              help=f"block-bootstrap 95% interval [{lo:.2f}, {hi:.2f}]")
    if lo < 0 < hi:
        st.warning(f"The interval [{lo:.2f}, {hi:.2f}] contains zero.")

    if bench:
        st.subheader("Spanning — is there anything new here?")
        res = E.spanning(r, clean[bench])
        s1, s2 = st.columns(2)
        s1.metric("Alpha per period", f"{res['alpha']:+.4f}")
        s2.metric("t-statistic", f"{res['alpha_t']:+.2f}")
        st.dataframe(pd.DataFrame({"beta": res["betas"], "t": res["beta_t"]}).round(3),
                     width="stretch")
        if abs(res["alpha_t"]) < 2:
            st.warning("Alpha is indistinguishable from zero: whatever this is, the "
                       "benchmarks already deliver it.")

    st.subheader("Costs — before anyone falls in love with the gross number")
    st.dataframe(C.cost_sensitivity(r, turn, bps_grid=(0, 5, 10, 20),
                                    periods_per_year=int(ppy)).round(4),
                 width="stretch")
    anat = D.cost_anatomy(float(r.mean()), float(turn), float(realistic),
                          periods_per_year=int(ppy))
    b1, b2 = st.columns(2)
    b1.metric("Breakeven cost", f"{anat['breakeven_cost_bps']:.1f} bps",
              help="the one-way cost at which the average period return reaches zero")
    b2.metric("Survives realistic costs", "yes" if anat["survives_costs"] else "no")

    with st.expander("Did a sealed block catch a false positive?"):
        st.caption("Enter the alpha and t-statistic from each block.")
        f1, f2, f3, f4 = st.columns(4)
        va = f1.number_input("Validation alpha", value=0.0068, format="%.4f")
        vt = f2.number_input("Validation t", value=2.41)
        ha = f3.number_input("Holdout alpha", value=-0.0029, format="%.4f")
        ht = f4.number_input("Holdout t", value=-0.62)
        fp = D.false_positive({"alpha": va, "alpha_t": vt}, {"alpha": ha, "alpha_t": ht})
        st.markdown(f"**{fp['verdict']}**")
        st.json(fp, expanded=False)

    with st.expander("Sealed holdout — register the opening"):
        st.caption("A sealed block opens once. Every opening is written to a ledger with "
                   "its reason and a fingerprint of the configuration; re-opening under a "
                   "changed configuration raises.")
        h1, h2 = st.columns(2)
        name = h1.text_input("Holdout name", value="holdout")
        ledger = h2.text_input("Ledger file", value="unseal_ledger.json")
        reason = st.text_input("Reason for opening it", value="final evaluation")
        config = st.text_area("Configuration fingerprinted with the opening",
                              value='{"model": "v1", "seeds": 3}', height=70)
        if st.button("Open the sealed block"):
            try:
                ledger_name = Path(ledger)
                if ledger_name.name != ledger or ledger_name.suffix.lower() != ".json":
                    raise ValueError("Ledger file must be a simple .json filename, not a path.")
                h = SealedHoldout(name, ROOT / ".verdict" / "holdouts" / ledger_name)
                rec = h.unseal(reason, json.loads(config))
                st.success(f"{rec['kind']} — {h.summary()}")
            except HoldoutAlreadyUnsealed as e:
                st.error(str(e))
            except json.JSONDecodeError:
                st.error("The configuration must be valid JSON.")

    with st.expander("Write the verdict"):
        t = st.text_input("Title", value="Verdict")
        cl = st.text_area("The claim audited", height=70)
        vd = st.text_area("The verdict", height=70)
        lim = st.text_area("Honest limitations — one per line. Required.", height=110,
                           help="The renderer refuses a verdict without them.")
        if st.button("Render", type="primary"):
            try:
                rep = VerdictReport(title=t, claim=cl, verdict=vd,
                                    honest_limitations=lines(lim))
                md = rep.render_markdown()
                st.download_button("Download the verdict", md,
                                   file_name=f"verdict-{date.today()}.md")
                st.markdown(md)
            except ValueError as e:
                st.error(f"**Not rendered.** {e}")


def page_agent() -> None:
    st.title("The agent")
    st.caption("Reads a claim, pre-registers a protocol, executes it through the library, "
               "and writes the verdict — without computing anything itself.")

    live = st.session_state.get("agent_live", False)
    try:
        import anthropic  # noqa: F401
        have_sdk = True
    except ModuleNotFoundError:
        have_sdk = False
    st.markdown(
        "**Offline** replays a recorded transcript for the model's turns while running "
        "every analysis for real — the whole loop, no credentials. "
        + ("**Live** is available: the SDK is installed."
           if have_sdk else
           "**Live** needs `pip install anthropic` and credentials in the environment.")
    )

    if st.button("Run the loop (offline)", type="primary"):
        from verdict.agent import demo, pipeline
        with st.spinner("running the protocol — the analysis is executing for real…"):
            run = pipeline.run_audit(
                demo.scripted_model(), demo.PAPER_STAND_IN,
                approve=lambda _claim, _protocol: True,
                case_id="complexity-voc",
            )
        st.session_state["agent_run"] = run.to_dict()

    run = st.session_state.get("agent_run")
    if not run:
        st.stop()

    st.subheader("Pre-registered, before any data was touched")
    st.markdown("**What would kill the claim**")
    for k in (run["protocol"] or {}).get("kill_criteria", []):
        st.markdown(f"- {k}")

    st.subheader("Execution")
    for step in run["tool_trace"]:
        if "tool" in step:
            args = ", ".join(f"{k}={v!r}" for k, v in step["arguments"].items())
            st.code(f"{step['tool']}({args})\n→ "
                    + json.dumps({k: v for k, v in (step.get("result") or {}).items()
                                  if not isinstance(v, str)}), language="text")

    st.subheader("The written verdict, and the audit of it")
    st.markdown(run["verdict_text"])
    audit = run["number_audit"]
    if audit.get("clean"):
        st.success(f"{audit['n_numbers']} figures written, every one traceable to a "
                   f"computed result.")
    else:
        st.error(f"Unsupported figures: {audit['unsupported']} — the model wrote these and "
                 "nothing computed them. The draft is withheld.")
    st.caption("What this check cannot catch: a correct number described wrongly. It bounds "
               "fabrication, not interpretation.")

    rep = ROOT / "cases/complexity/agent_eval/report.md"
    if rep.exists():
        with st.expander("How the drafted protocol scores against expert practice"):
            st.markdown(rep.read_text())


def _paper_provider_options() -> dict[str, str | None]:
    options = {"No matching Verdict adapter — protocol only": None}
    for case_id, spec in CASE_BY_ID.items():
        if spec.role == "data-gated":
            continue
        mode = "executable" if spec.agent_mode == "executable" else "read-only evidence"
        options[f"{case_id} ({mode})"] = case_id
    return options


def page_paper_audit() -> None:
    """The visible B-layer entry: paper text → protocol → approval → bounded outcome."""
    st.title("Audit a paper")
    st.caption("Paper text → claim card → pre-registered protocol → human approval → "
               "deterministic provider or honest data-gated stop.")
    st.info("A paper alone never creates a verdict. Select a Verdict adapter only when it "
            "actually matches the paper and its data. Otherwise the correct outcome is an "
            "approved, data-gated protocol — not an invented replication.")

    mode = st.radio("Paper input", ["Paste or upload a paper", "Offline Complexity walkthrough"],
                    horizontal=True)
    paper_text = ""
    origin = ""
    if mode == "Offline Complexity walkthrough":
        from verdict.agent import demo
        paper_text, origin = demo.PAPER_STAND_IN, "offline Complexity fixture summary"
        st.caption("This is a fixed demonstration summary, not a PDF and not a measurement "
                   "of model capability. Its tools compute against the pinned Complexity data.")
    else:
        source = st.radio("Text source", ["Paste text", "Upload a file"], horizontal=True)
        if source == "Paste text":
            paper_text = st.text_area("Paper text", height=240,
                                      placeholder="Paste the abstract, methods, and main results here.")
            origin = "pasted text"
        else:
            uploaded = st.file_uploader("Paper file", type=["txt", "md", "markdown", "pdf"])
            if uploaded is not None:
                from verdict.agent.paper import paper_text as decode_paper
                try:
                    paper_text = decode_paper(uploaded.getvalue(), uploaded.name)
                    origin = uploaded.name
                    st.caption(f"Extracted {len(paper_text):,} characters from `{uploaded.name}`.")
                except (ValueError, ModuleNotFoundError) as exc:
                    st.error(str(exc))

    choices = _paper_provider_options()
    chosen_label = st.selectbox("Execution route", list(choices), index=0,
                                help="Choose a route only when its claim and data match the paper.")
    chosen_case = choices[chosen_label]
    if mode == "Offline Complexity walkthrough":
        chosen_case = "complexity-voc"
        st.caption("Execution route fixed to `complexity-voc` for the offline walkthrough.")

    if st.button("Extract claim and draft protocol", type="primary"):
        if not paper_text.strip():
            st.error("Paste or upload paper text first.")
        else:
            try:
                if mode == "Offline Complexity walkthrough":
                    from verdict.agent import demo
                    model = demo.scripted_model()
                else:
                    from verdict.agent.llm import AnthropicModel
                    model = AnthropicModel()
                from verdict.agent import pipeline, providers
                available_tools = (providers.get_provider(chosen_case).definitions()
                                   if chosen_case else [])
                claim = pipeline.extract_claim(model, paper_text)
                protocol = pipeline.draft_protocol(
                    model, claim, available_tools=[tool["name"] for tool in available_tools])
                st.session_state["paper_audit"] = {
                    "origin": origin,
                    "case_id": chosen_case,
                    "claim": claim.to_dict(),
                    "protocol": protocol.to_dict(),
                }
                st.session_state["paper_audit_model"] = model
                st.session_state.pop("paper_audit_run", None)
            except Exception as exc:
                st.error(f"Could not draft a protocol: {type(exc).__name__}: {exc}")

    draft = st.session_state.get("paper_audit")
    if not draft:
        return
    st.divider()
    st.subheader("1 · Claim extracted from the paper")
    st.caption(f"Source: {draft['origin']}")
    st.json(draft["claim"], expanded=False)
    st.subheader("2 · Protocol fixed before execution")
    st.json(draft["protocol"], expanded=False)

    approved = st.checkbox("I approve this protocol exactly as written.", key="paper_audit_approved")
    action = ("Execute through the selected provider" if draft["case_id"]
              else "Record protocol-ready, data-gated outcome")
    if st.button(action, type="primary"):
        if not approved:
            st.warning("Nothing executed: approve the displayed protocol first.")
        else:
            try:
                from verdict.agent import pipeline
                from verdict.agent.schema import ClaimCard, Protocol
                claim = ClaimCard.from_dict(draft["claim"])
                protocol = Protocol.from_dict(draft["protocol"])
                if draft["case_id"]:
                    with st.spinner("running deterministic tools under the approved protocol…"):
                        run = pipeline.execute_approved_protocol(
                            st.session_state["paper_audit_model"], claim, protocol,
                            draft["case_id"])
                else:
                    run = pipeline.data_gated_audit(
                        claim, protocol,
                        "no matching Verdict data/provider adapter was selected for this paper")
                st.session_state["paper_audit_run"] = run.to_dict()
            except Exception as exc:
                st.error(f"Audit stopped: {type(exc).__name__}: {exc}")

    run = st.session_state.get("paper_audit_run")
    if not run:
        return
    st.subheader("3 · Audit outcome")
    st.write(f"**State:** `{run['state']}` · **Mode:** `{run['execution_mode']}`")
    for note in run.get("notes", []):
        st.caption(note)
    if run["state"] == "protocol-ready-data-gated":
        st.info("No verdict was issued. The paper now has a fixed, reviewable protocol; "
                "execution starts only after a matching data and provider adapter exists.")
    if run.get("tool_trace"):
        st.json(run["tool_trace"], expanded=False)
    if run.get("verdict_text"):
        st.markdown(run["verdict_text"])
        audit = run.get("number_audit") or {}
        if audit.get("clean"):
            st.success("Every written figure traces to the selected provider's tool output.")
        else:
            st.error(f"Draft withheld: unsupported figures {audit.get('unsupported', [])}.")


PAGES = {"Start here": page_start_here, "Audit a paper": page_paper_audit,
         "The register": page_register, "New claim": page_new_claim,
         "Evaluate a result": page_evaluate, "The agent": page_agent}

with st.sidebar:
    st.markdown("## ⚖ Verdict")
    st.caption("A harness for checking predictive claims.")
    choice = st.radio("Section", list(PAGES), label_visibility="collapsed", key="section")
    st.divider()
    st.caption("Every figure on every screen is computed by the library, not by this "
               "interface. Analysis lives in `verdict/`; this file only collects inputs "
               "and shows results.")

PAGES[choice]()
