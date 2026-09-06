# Agent evaluation — protocol coverage against expert practice

Coverage: **6/10** (60%) of the checks human auditors performed.

**This scores a fixture, not the model.** The protocol came from a scripted offline run, so the coverage below measures the transcript's author. It exercises the eval machinery end to end; it is not a measurement of agent capability. Re-run with a live model and the paper itself for that.

## Covered

- **Span the strategy against a mechanical momentum / volatility-timing benchmark** (mechanism critique) — matched: “a simple momentum rule on past returns, to check the complex model is adding something a trivial alternative would not produce”
- **Counterfactual: inject reversal into returns and check the model changes behaviour** (mechanism critique) — matched: “inject reversal into the returns as a counterfactual and check whether the strategy's behaviour changes”
- **Formal forecast-accuracy test rather than strategy Sharpe alone** (standard practice) — matched: “run a formal forecast-accuracy test rather than relying on the strategy Sharpe alone”
- **Charge realistic trading frictions** (standard practice) — matched: “charge realistic transaction costs against turnover before concluding that any timing performance is usable”
- **Check the result holds across subsamples rather than one stretch** (standard practice) — matched: “check the result across subsamples rather than one continuous stretch”
- **Report variation across random-feature draws rather than one seed** (standard practice) — matched: “vary the random-feature seed and report the spread across draws”

## Missed — what the agent did not think of

- **Test whether the over-parameterized model is equivalent to a simple kernel smoother** (mechanism critique)
- **Counterfactual: destroy the predictors' information but keep their persistence** (mechanism critique)
- **Test sensitivity to the zero-intercept constraint** (implementation critique)
- **Test sensitivity to the performance-aggregation convention** (implementation critique)

## Proposed but not on the checklist

- “a no-predictability benchmark forecast of zero”
- “reproduce the reported rise in Sharpe as the number of features grows”
- “the forecast fails a formal accuracy test against the no-predictability benchmark”
- “a trivial alternative rule spans the strategy's returns”
- “performance is unchanged on data where the claimed effect could not exist”
- “strictly chronological; forecasts use only data from before the forecast month, with the rolling window never reaching forward”

These are not automatically credited: a check the experts did not run may be a good idea, a restatement of one they did, or padding.

## Honest limitations

- Matching is one-to-one keyword matching; a correct test described in unanticipated words scores as a miss.
- One checklist, one claim, one run: this measures whether the agent proposes the right tests on a case whose answer is already known, not whether it would on a fresh one.
- The checklist itself is a judgment about what mattered, assembled from the published critiques after the fact.
- Coverage is not correctness: proposing a test is not running it, and the execution stage is scored separately by whether its numbers survive the audit.
