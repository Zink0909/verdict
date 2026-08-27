"""An offline transcript, so the loop can be demonstrated and tested without a key.

What is real here and what is not, stated plainly because the distinction is the
whole point of the system:

* **Real** — every number. The tool calls below execute the framework against
  the pinned dataset at run time, and the write step composes its prose around
  whatever those calls actually returned.
* **A fixture** — the model's turns. The claim card, the protocol, and the
  choice of which tools to call are recorded text, not a model's output.

So this demonstrates the machinery end to end and gives the regression suite
something deterministic to bite on. It does **not** measure the model: a
protocol written by hand and then scored against a checklist would be scoring
its author. `scripts/run_agent_eval.py` refuses to present a scripted run as a
measurement for that reason.
"""
from __future__ import annotations

import json

from .llm import Reply, ScriptedModel

# A summary of the audited claim, standing in for the paper's text. Written from
# the case's own pinned construction notes — not the PDF.
PAPER_STAND_IN = """\
[OFFLINE FIXTURE — a summary of the audited claim, not the paper itself.]

The Virtue of Complexity in Return Prediction (Kelly, Malamud and Zhou, Journal
of Finance 2024). The paper takes fifteen standard monthly predictors of the US
market return and expands them into up to twelve thousand random Fourier
features, then fits a ridge regression — including the ridgeless limit — in
rolling windows as short as twelve months, and times the market with the
resulting forecast. It reports that out-of-sample market-timing performance
*rises* with the number of features, with an annualized Sharpe ratio around 0.4
at the largest model, and that this holds even in the twelve-month window where
parameters vastly outnumber observations. The paper presents this as evidence
that benign overfitting extends to return prediction: more complexity is better,
against the conventional view that extracting signal from noisy, persistent
predictors requires decades of data.
"""

CLAIM = {
    "signal": "ridge (including ridgeless) regression on up to 12,000 random Fourier "
              "features built from 15 standard monthly market predictors, refit in rolling "
              "windows as short as 12 months; position proportional to the forecast",
    "universe": "the aggregate US equity market (market timing, not cross-section)",
    "frequency": "monthly",
    "claimed_effect": "out-of-sample timing Sharpe rises with the number of features, "
                      "reaching roughly 0.4 at 12,000 features, and holds at a 12-month window",
    "sample": "monthly US data, 1926 onward",
    "source": "Kelly, Malamud and Zhou (2024), Journal of Finance",
    "data_needs": ["the 15 standard monthly predictors", "monthly market excess returns"],
}

# Deliberately partial: it covers the obvious evaluation hygiene and one
# counterfactual, and misses the mechanism tests that decided the real debate.
PROTOCOL = {
    "data_requirements": ["the 15 standard monthly predictors, standardized with "
                          "backward-looking windows only", "monthly market excess returns"],
    "splits": "strictly chronological; forecasts use only data from before the forecast "
              "month, with the rolling window never reaching forward",
    "benchmarks": ["a no-predictability benchmark forecast of zero",
                   "a simple momentum rule on past returns, to check the complex model is "
                   "adding something a trivial alternative would not produce"],
    "cost_model": "charge realistic transaction costs against turnover before concluding "
                  "that any timing performance is usable",
    "diagnostics": ["reproduce the reported rise in Sharpe as the number of features grows",
                    "run a formal forecast-accuracy test rather than relying on the "
                    "strategy Sharpe alone",
                    "inject reversal into the returns as a counterfactual and check whether "
                    "the strategy's behaviour changes"],
    "robustness": ["vary the random-feature seed and report the spread across draws",
                   "check the result across subsamples rather than one continuous stretch"],
    "kill_criteria": ["the forecast fails a formal accuracy test against the "
                      "no-predictability benchmark",
                      "a trivial alternative rule spans the strategy's returns",
                      "performance is unchanged on data where the claimed effect could not exist"],
    "rationale": "The claim is about out-of-sample forecast quality, so the protocol tests "
                 "forecast quality directly rather than accepting a strategy Sharpe as proof, "
                 "and asks whether a simpler mechanism would produce the same result.",
}

_CALLS = [
    ("describe_dataset", {}),
    ("run_complex_model", {"n_features": 60, "window": 12, "shrinkage": 0.001, "seeds": 2}),
    ("run_complex_model", {"n_features": 1200, "window": 12, "shrinkage": 0.001, "seeds": 2}),
    ("forecast_comparison_test", {"n_features": 1200, "window": 12, "seeds": 2}),
    ("counterfactual_world", {"kind": "reversal", "n_features": 1200, "window": 12,
                              "draws": 3, "seeds": 2}),
]


def _write_turn(plant_error: bool):
    """Compose the verdict from whatever the tools actually returned this run."""

    def turn(system, messages, tools, schema, effort) -> Reply:
        results = json.loads(messages[-1]["content"].split("Results:\n", 1)[1]
                             .split("\n\nWrite the verdict.")[0])
        by_tool: dict[str, list[dict]] = {}
        for step in results:
            by_tool.setdefault(step["tool"], []).append(step["result"])
        small, large = by_tool["run_complex_model"][0], by_tool["run_complex_model"][-1]
        cw = by_tool["forecast_comparison_test"][0]
        rev = by_tool["counterfactual_world"][0]
        data = by_tool["describe_dataset"][0]
        # Wording is derived from the values, never asserted independently of them:
        # a fixture that hard-codes "negative" is exactly the failure the number
        # audit cannot catch (see guardrails: a correct figure, described wrongly).
        r2_word = "negative" if large["oos_r2"] < 0 else "barely positive"
        cw_beats = cw["rejects_equal_accuracy_5pct"]
        cw_word = ("does beat the no-predictability benchmark by a formal test of accuracy, "
                   "so at this configuration forecast quality is not obviously absent"
                   if cw_beats else
                   "does not beat the no-predictability benchmark by a formal test of accuracy")
        text = (
            f"The claim reproduces in direction: on {data['observations']} monthly "
            f"observations the timing Sharpe rises from {small['sharpe_annualized']} at "
            f"{small['n_features']} features to {large['sharpe_annualized']} at "
            f"{large['n_features']}, with an out-of-sample R-squared of {large['oos_r2']} "
            f"({r2_word}).\n\n"
            f"The formal forecast test is the first real check: the Clark-West statistic is "
            f"{cw['clark_west_t']}, which {cw_word}.\n\n"
            f"The counterfactual is decisive whichever way that went. Injecting reversal into "
            f"the returns takes the strategy from {rev['sharpe_real_data']} to "
            f"{rev['sharpe_counterfactual_mean']}, negative in "
            f"{rev['share_negative']:.0%} of draws. The model does not learn what the data "
            f"rewards; it builds the same positions regardless.\n\n"
            f"Honest limitations: this run used {large['n_features']} features rather than the "
            f"paper's largest configuration, a small number of seeds, and did not test the "
            f"implementation conventions the paper's own critics raised. It also did not "
            f"identify what the model is doing instead — only that it is not learning."
        )
        if plant_error:
            text += ("\n\nThe effect is strongest in the 1970s, where the strategy returned "
                     "18.4 percent annually.")
        return Reply(text=text)

    return turn


def scripted_model(plant_error: bool = False) -> ScriptedModel:
    """The fixture transcript: extract, pre-register, five tool calls, then write."""
    turns: list = [ScriptedModel.json_reply(CLAIM), ScriptedModel.json_reply(PROTOCOL)]
    turns += [ScriptedModel.tool_reply(name, args, call_id=f"call_{i}")
              for i, (name, args) in enumerate(_CALLS)]
    turns.append(Reply(text="The protocol's questions are answered."))
    turns.append(_write_turn(plant_error))
    return ScriptedModel(turns)
